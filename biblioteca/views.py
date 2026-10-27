from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count, F, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from .forms import AuthorForm, BookForm, BookSearchForm, ReviewForm, SignUpForm
from .models import Author, Book, Loan, Review


class LibrarianRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Solo el rol Bibliotecario (usuarios staff) gestiona el catálogo y todos los préstamos."""

    def test_func(self):
        return self.request.user.is_staff


def signup(request):
    if request.user.is_authenticated:
        return redirect('book_list')
    form = SignUpForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, f'¡Bienvenido, {user.username}! Ya puedes pedir libros en préstamo.')
        return redirect('book_list')
    return render(request, 'registration/signup.html', {'form': form})


# ---------- Catálogo ----------

class BookListView(ListView):
    """Catálogo público con buscador avanzado."""

    model = Book
    paginate_by = 12
    template_name = 'biblioteca/book_list.html'

    def get_queryset(self):
        qs = Book.objects.with_stats().annotate(n_loans=Count('loans', distinct=True)).select_related('genre').prefetch_related('authors')
        self.form = BookSearchForm(self.request.GET or None)
        orden = 'title'
        if self.form.is_valid():
            d = self.form.cleaned_data
            if d['q']:
                isbn = d['q'].replace('-', '').replace(' ', '')
                qs = qs.filter(Q(title__icontains=d['q']) | Q(isbn__icontains=isbn))
            if d['author']:
                qs = qs.filter(authors__name__icontains=d['author'])
            if d['genre']:
                qs = qs.filter(genre=d['genre'])
            if d['year_from']:
                qs = qs.filter(year__gte=d['year_from'])
            if d['year_to']:
                qs = qs.filter(year__lte=d['year_to'])
            if d['min_rating']:
                qs = qs.filter(avg_rating__gte=d['min_rating'])
            if d['available']:
                qs = qs.filter(active_loans__lt=F('copies'))
            orden = d['order'] or 'title'
        if orden.lstrip('-') in ('avg_rating', 'year'):
            qs = qs.order_by(F(orden.lstrip('-')).desc(nulls_last=True), 'title')
        else:
            qs = qs.order_by(orden, 'title')
        return qs.distinct()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form'] = self.form
        params = self.request.GET.copy()
        params.pop('page', None)
        ctx['query_string'] = params.urlencode()
        return ctx


class BookDetailView(DetailView):
    model = Book
    template_name = 'biblioteca/book_detail.html'

    def get_queryset(self):
        return Book.objects.with_stats().select_related('genre').prefetch_related('authors')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        libro = self.object
        ctx['reviews'] = libro.reviews.select_related('user')
        if user.is_authenticated:
            ctx['my_loan'] = libro.loans.active().filter(user=user).first()
            ya_leido = libro.loans.filter(user=user).exists()
            mi_resena = libro.reviews.filter(user=user).first()
            ctx['my_review'] = mi_resena
            # Solo puede reseñar quien lo ha tenido en préstamo, y una vez
            ctx['can_review'] = ya_leido and mi_resena is None
            ctx['review_form'] = ReviewForm()
            if user.is_staff:
                ctx['active_loans_list'] = libro.loans.active().select_related('user')
        return ctx


class BookCreateView(LibrarianRequiredMixin, SuccessMessageMixin, CreateView):
    model = Book
    form_class = BookForm
    success_message = 'Libro «%(title)s» añadido al catálogo.'


class BookUpdateView(LibrarianRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Book
    form_class = BookForm
    success_message = 'Libro «%(title)s» actualizado.'


class AuthorListView(ListView):
    model = Author
    queryset = Author.objects.annotate(n_books=Count('books'))


class AuthorDetailView(DetailView):
    model = Author


class AuthorCreateView(LibrarianRequiredMixin, SuccessMessageMixin, CreateView):
    model = Author
    form_class = AuthorForm
    success_message = 'Autor «%(name)s» creado.'


class AuthorUpdateView(LibrarianRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Author
    form_class = AuthorForm
    success_message = 'Autor «%(name)s» actualizado.'


# ---------- Préstamos ----------

@login_required
@require_POST
def borrow(request, pk):
    libro = get_object_or_404(Book, pk=pk)
    try:
        prestamo = Loan.lend(libro, request.user)
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
    else:
        messages.success(request, f'Préstamo registrado. Devuelve «{libro}» antes del {prestamo.due_date:%d/%m/%Y}.')
    return redirect(libro)


@login_required
@require_POST
def return_loan(request, pk):
    prestamo = get_object_or_404(Loan.objects.select_related('book'), pk=pk)
    # El socio devuelve los suyos; el bibliotecario puede registrar cualquier devolución
    if prestamo.user != request.user and not request.user.is_staff:
        raise PermissionDenied
    try:
        prestamo.mark_returned()
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
    else:
        retraso = ' (con retraso)' if prestamo.due_date < prestamo.returned_at else ''
        messages.success(request, f'Devolución de «{prestamo.book}» registrada{retraso}.')
    return redirect(request.POST.get('next') or 'my_loans')


@login_required
def my_loans(request):
    """Historial de préstamos del socio: activos y devueltos."""
    prestamos = request.user.loans.select_related('book').prefetch_related('book__authors')
    return render(request, 'biblioteca/my_loans.html', {
        'active': [p for p in prestamos if p.is_active],
        'history': [p for p in prestamos if not p.is_active],
    })


class LoanAdminListView(LibrarianRequiredMixin, ListView):
    """Vista del bibliotecario: todos los préstamos, con filtro de estado."""

    model = Loan
    paginate_by = 25
    template_name = 'biblioteca/loan_admin_list.html'

    def get_queryset(self):
        qs = Loan.objects.select_related('book', 'user')
        estado = self.request.GET.get('estado', 'activos')
        if estado == 'activos':
            qs = qs.active()
        elif estado == 'vencidos':
            qs = qs.overdue()
        elif estado == 'devueltos':
            qs = qs.filter(returned_at__isnull=False)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['estado'] = self.request.GET.get('estado', 'activos')
        ctx['query_string'] = f"estado={ctx['estado']}"
        return ctx


# ---------- Reseñas ----------

@login_required
@require_POST
def add_review(request, pk):
    libro = get_object_or_404(Book, pk=pk)
    if not libro.loans.filter(user=request.user).exists():
        messages.error(request, 'Solo puedes valorar libros que hayas tenido en préstamo.')
        return redirect(libro)
    if libro.reviews.filter(user=request.user).exists():
        messages.error(request, 'Ya has valorado este libro.')
        return redirect(libro)
    form = ReviewForm(request.POST)
    if form.is_valid():
        resena = form.save(commit=False)
        resena.book = libro
        resena.user = request.user
        resena.save()
        messages.success(request, '¡Gracias por tu reseña!')
    else:
        messages.error(request, 'Revisa la valoración.')
    return redirect(libro)


@login_required
@require_POST
def delete_review(request, pk):
    resena = get_object_or_404(Review, pk=pk)
    if resena.user != request.user and not request.user.is_staff:
        raise PermissionDenied
    libro = resena.book
    resena.delete()
    messages.success(request, 'Reseña eliminada.')
    return redirect(libro)
