from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.db.models import Avg, Count, Q
from django.urls import reverse
from django.utils import timezone


class Author(models.Model):
    name = models.CharField('nombre', max_length=120, unique=True)
    bio = models.TextField('biografía', blank=True)
    birth_year = models.PositiveSmallIntegerField('año de nacimiento', null=True, blank=True)

    class Meta:
        verbose_name = 'autor'
        verbose_name_plural = 'autores'
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('author_detail', args=[self.pk])


class Genre(models.Model):
    name = models.CharField('nombre', max_length=60, unique=True)

    class Meta:
        verbose_name = 'género'
        verbose_name_plural = 'géneros'
        ordering = ['name']

    def __str__(self):
        return self.name


class BookQuerySet(models.QuerySet):
    def with_stats(self):
        """Añade préstamos activos, nota media y número de reseñas en una sola consulta."""
        return self.annotate(
            active_loans=Count('loans', filter=Q(loans__returned_at__isnull=True), distinct=True),
            avg_rating=Avg('reviews__rating'),
            n_reviews=Count('reviews', distinct=True),
        )


class Book(models.Model):
    title = models.CharField('título', max_length=200)
    authors = models.ManyToManyField(Author, verbose_name='autores', related_name='books')
    genre = models.ForeignKey(Genre, verbose_name='género', on_delete=models.SET_NULL, null=True, blank=True, related_name='books')
    isbn = models.CharField('ISBN', max_length=17, unique=True, help_text='10 o 13 dígitos, con o sin guiones')
    year = models.PositiveSmallIntegerField('año', null=True, blank=True)
    description = models.TextField('sinopsis', blank=True)
    cover = models.ImageField('portada', upload_to='portadas/', blank=True)
    copies = models.PositiveSmallIntegerField('ejemplares', default=1, validators=[MinValueValidator(1)])
    created_at = models.DateTimeField(auto_now_add=True)

    objects = BookQuerySet.as_manager()

    class Meta:
        verbose_name = 'libro'
        verbose_name_plural = 'libros'
        ordering = ['title']

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('book_detail', args=[self.pk])

    def clean(self):
        digitos = self.isbn.replace('-', '').replace(' ', '')
        if len(digitos) not in (10, 13) or not digitos[:-1].isdigit():
            raise ValidationError({'isbn': 'El ISBN debe tener 10 o 13 dígitos.'})

    @property
    def available_copies(self):
        activos = getattr(self, 'active_loans', None)
        if activos is None:
            activos = self.loans.filter(returned_at__isnull=True).count()
        return max(self.copies - activos, 0)


class LoanQuerySet(models.QuerySet):
    def active(self):
        return self.filter(returned_at__isnull=True)

    def overdue(self):
        return self.active().filter(due_date__lt=timezone.localdate())


class Loan(models.Model):
    book = models.ForeignKey(Book, verbose_name='libro', on_delete=models.PROTECT, related_name='loans')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='socio', on_delete=models.CASCADE, related_name='loans')
    loan_date = models.DateField('fecha de préstamo', default=timezone.localdate)
    due_date = models.DateField('devolver antes de')
    returned_at = models.DateField('devuelto el', null=True, blank=True)

    objects = LoanQuerySet.as_manager()

    class Meta:
        verbose_name = 'préstamo'
        verbose_name_plural = 'préstamos'
        ordering = ['-loan_date', '-pk']
        constraints = [
            # Un socio no puede tener dos préstamos activos del mismo libro
            models.UniqueConstraint(fields=['book', 'user'], condition=Q(returned_at__isnull=True), name='un_prestamo_activo_por_libro'),
        ]

    def __str__(self):
        return f'{self.book} → {self.user}'

    @property
    def is_active(self):
        return self.returned_at is None

    @property
    def is_overdue(self):
        return self.is_active and self.due_date < timezone.localdate()

    @classmethod
    def lend(cls, book, user):
        """Crea un préstamo comprobando disponibilidad y el límite del socio."""
        with transaction.atomic():
            book = Book.objects.select_for_update().get(pk=book.pk)
            if book.loans.active().filter(user=user).exists():
                raise ValidationError('Ya tienes este libro en préstamo.')
            if book.loans.active().count() >= book.copies:
                raise ValidationError('No quedan ejemplares disponibles de este libro.')
            if user.loans.active().count() >= settings.MAX_ACTIVE_LOANS:
                raise ValidationError(f'Has alcanzado el máximo de {settings.MAX_ACTIVE_LOANS} préstamos activos.')
            if user.loans.overdue().exists():
                raise ValidationError('Tienes préstamos vencidos: devuélvelos antes de pedir otro.')
            hoy = timezone.localdate()
            return cls.objects.create(book=book, user=user, loan_date=hoy, due_date=hoy + timedelta(days=settings.LOAN_DAYS))

    def mark_returned(self):
        if not self.is_active:
            raise ValidationError('Este préstamo ya estaba devuelto.')
        self.returned_at = timezone.localdate()
        self.save(update_fields=['returned_at'])


class Review(models.Model):
    book = models.ForeignKey(Book, verbose_name='libro', on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='socio', on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveSmallIntegerField('valoración', validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField('comentario', blank=True, max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'reseña'
        verbose_name_plural = 'reseñas'
        ordering = ['-created_at']
        constraints = [models.UniqueConstraint(fields=['book', 'user'], name='una_resena_por_libro')]

    def __str__(self):
        return f'{self.rating}★ {self.book} ({self.user})'
