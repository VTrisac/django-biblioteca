from datetime import timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Author, Book, Genre, Loan, Review


class BaseTest(TestCase):
    def setUp(self):
        self.socio = User.objects.create_user('socio', password='pass12345!')
        self.otro = User.objects.create_user('otro', password='pass12345!')
        self.biblio = User.objects.create_user('biblio', password='pass12345!', is_staff=True)
        self.autor = Author.objects.create(name='Ana María Matute')
        self.genero = Genre.objects.create(name='Novela')
        self.libro = Book.objects.create(title='Olvidado Rey Gudú', isbn='9788467036084', year=1996, copies=1, genre=self.genero)
        self.libro.authors.add(self.autor)


class LoanModelTests(BaseTest):
    def test_prestamo_y_devolucion(self):
        p = Loan.lend(self.libro, self.socio)
        self.assertEqual(p.due_date, timezone.localdate() + timedelta(days=14))
        self.assertEqual(self.libro.available_copies, 0)
        p.mark_returned()
        self.assertEqual(Book.objects.get(pk=self.libro.pk).available_copies, 1)
        with self.assertRaises(ValidationError):
            p.mark_returned()

    def test_sin_ejemplares(self):
        Loan.lend(self.libro, self.socio)
        with self.assertRaisesMessage(ValidationError, 'No quedan ejemplares'):
            Loan.lend(self.libro, self.otro)

    def test_no_repetir_el_mismo_libro(self):
        self.libro.copies = 2
        self.libro.save()
        Loan.lend(self.libro, self.socio)
        with self.assertRaisesMessage(ValidationError, 'Ya tienes este libro'):
            Loan.lend(self.libro, self.socio)

    @override_settings(MAX_ACTIVE_LOANS=2)
    def test_limite_de_prestamos(self):
        for i in range(2):
            b = Book.objects.create(title=f'L{i}', isbn=f'978000000000{i}')
            Loan.lend(b, self.socio)
        with self.assertRaisesMessage(ValidationError, 'máximo de 2'):
            Loan.lend(self.libro, self.socio)

    def test_bloqueo_por_prestamo_vencido(self):
        b = Book.objects.create(title='Viejo', isbn='9780000000009')
        p = Loan.lend(b, self.socio)
        Loan.objects.filter(pk=p.pk).update(due_date=timezone.localdate() - timedelta(days=1))
        self.assertTrue(Loan.objects.get(pk=p.pk).is_overdue)
        with self.assertRaisesMessage(ValidationError, 'vencidos'):
            Loan.lend(self.libro, self.socio)

    def test_isbn_invalido(self):
        b = Book(title='X', isbn='123')
        with self.assertRaises(ValidationError):
            b.full_clean()


class ViewTests(BaseTest):
    def test_catalogo_publico(self):
        r = self.client.get(reverse('book_list'))
        self.assertContains(r, 'Olvidado Rey Gudú')

    def test_prestar_requiere_login(self):
        r = self.client.post(reverse('borrow', args=[self.libro.pk]))
        self.assertEqual(r.status_code, 302)
        self.assertFalse(Loan.objects.exists())

    def test_flujo_prestamo_devolucion_y_historial(self):
        self.client.login(username='socio', password='pass12345!')
        self.client.post(reverse('borrow', args=[self.libro.pk]))
        prestamo = Loan.objects.get()
        r = self.client.get(reverse('my_loans'))
        self.assertContains(r, 'En préstamo ahora')
        self.assertContains(r, 'Olvidado Rey Gudú')
        self.client.post(reverse('return_loan', args=[prestamo.pk]))
        prestamo.refresh_from_db()
        self.assertIsNotNone(prestamo.returned_at)

    def test_no_devolver_prestamo_ajeno(self):
        p = Loan.lend(self.libro, self.otro)
        self.client.login(username='socio', password='pass12345!')
        self.assertEqual(self.client.post(reverse('return_loan', args=[p.pk])).status_code, 403)
        self.client.login(username='biblio', password='pass12345!')
        self.client.post(reverse('return_loan', args=[p.pk]))
        p.refresh_from_db()
        self.assertIsNotNone(p.returned_at)

    def test_resena_solo_si_lo_ha_tenido(self):
        self.client.login(username='socio', password='pass12345!')
        url = reverse('add_review', args=[self.libro.pk])
        self.client.post(url, {'rating': 5, 'comment': 'Genial'})
        self.assertFalse(Review.objects.exists())
        Loan.lend(self.libro, self.socio)
        self.client.post(url, {'rating': 5, 'comment': 'Genial'})
        self.client.post(url, {'rating': 1, 'comment': 'Otra vez'})
        self.assertEqual(Review.objects.count(), 1)
        r = self.client.get(self.libro.get_absolute_url())
        self.assertContains(r, '★★★★★')

    def test_buscador_avanzado(self):
        otro = Book.objects.create(title='Cien años de soledad', isbn='9788497592208', year=1967)
        otro.authors.add(Author.objects.create(name='Gabriel García Márquez'))
        r = self.client.get(reverse('book_list'), {'author': 'garcía'})
        self.assertContains(r, 'Cien años')
        self.assertNotContains(r, 'Olvidado Rey')
        r = self.client.get(reverse('book_list'), {'year_from': 1990})
        self.assertContains(r, 'Olvidado Rey')
        self.assertNotContains(r, 'Cien años')
        Loan.lend(self.libro, self.socio)
        r = self.client.get(reverse('book_list'), {'available': 'on'})
        self.assertNotContains(r, 'Olvidado Rey')
        r = self.client.get(reverse('book_list'), {'q': '978-84-9759'})
        self.assertContains(r, 'Cien años')

    def test_socio_no_crea_libros(self):
        self.client.login(username='socio', password='pass12345!')
        self.assertEqual(self.client.get(reverse('book_create')).status_code, 403)
        self.client.login(username='biblio', password='pass12345!')
        self.assertEqual(self.client.get(reverse('book_create')).status_code, 200)

    def test_gestion_prestamos_solo_bibliotecario(self):
        self.client.login(username='socio', password='pass12345!')
        self.assertEqual(self.client.get(reverse('loan_admin_list')).status_code, 403)
        Loan.lend(self.libro, self.socio)
        self.client.login(username='biblio', password='pass12345!')
        r = self.client.get(reverse('loan_admin_list'), {'estado': 'activos'})
        self.assertContains(r, 'socio')
