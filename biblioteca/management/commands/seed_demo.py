"""Crea usuarios de prueba (uno por rol), catálogo de ejemplo, préstamos y reseñas. Es idempotente."""
import io
import random
import textwrap
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone
from PIL import Image, ImageDraw, ImageFont

from biblioteca.models import Author, Book, Genre, Loan, Review

LIBROS = [
    ('Cien años de soledad', 'Gabriel García Márquez', 'Novela', 1967, '9788497592208'),
    ('El amor en los tiempos del cólera', 'Gabriel García Márquez', 'Novela', 1985, '9788497592437'),
    ('La sombra del viento', 'Carlos Ruiz Zafón', 'Novela', 2001, '9788408163435'),
    ('Rayuela', 'Julio Cortázar', 'Novela', 1963, '9788437604572'),
    ('Ficciones', 'Jorge Luis Borges', 'Relatos', 1944, '9788499089508'),
    ('El Aleph', 'Jorge Luis Borges', 'Relatos', 1949, '9788499089515'),
    ('Fundación', 'Isaac Asimov', 'Ciencia ficción', 1951, '9788497593793'),
    ('Yo, robot', 'Isaac Asimov', 'Ciencia ficción', 1950, '9788435021050'),
    ('Dune', 'Frank Herbert', 'Ciencia ficción', 1965, '9788497596824'),
    ('1984', 'George Orwell', 'Ciencia ficción', 1949, '9788499890944'),
    ('Rebelión en la granja', 'George Orwell', 'Novela', 1945, '9788499890951'),
    ('El nombre de la rosa', 'Umberto Eco', 'Misterio', 1980, '9788426403568'),
    ('Diez negritos', 'Agatha Christie', 'Misterio', 1939, '9788467045390'),
    ('Asesinato en el Orient Express', 'Agatha Christie', 'Misterio', 1934, '9788467045413'),
    ('Sapiens', 'Yuval Noah Harari', 'Ensayo', 2011, '9788499926223'),
    ('Breve historia del tiempo', 'Stephen Hawking', 'Ensayo', 1988, '9788498920550'),
]
COMENTARIOS = ['Imprescindible.', 'Me ha encantado de principio a fin.', 'Muy bien escrito, aunque algo lento al principio.',
               'Una relectura obligada.', 'No es para todos, pero merece la pena.', '']


def generar_portada(titulo, autor, semilla):
    """Portada sencilla generada con Pillow: color de fondo, título y autor."""
    rnd = random.Random(semilla)
    fondo = tuple(rnd.randint(40, 140) for _ in range(3))
    img = Image.new('RGB', (400, 600), fondo)
    dibujo = ImageDraw.Draw(img)
    dibujo.rectangle([20, 20, 380, 580], outline=(255, 255, 255), width=3)
    try:
        grande = ImageFont.truetype('DejaVuSerif-Bold.ttf', 38)
        pequena = ImageFont.truetype('DejaVuSans.ttf', 24)
    except OSError:
        grande = pequena = ImageFont.load_default()
    y = 140
    for linea in textwrap.wrap(titulo, 16):
        dibujo.text((200, y), linea, font=grande, fill=(255, 255, 255), anchor='mm')
        y += 50
    dibujo.text((200, 500), autor, font=pequena, fill=(240, 230, 210), anchor='mm')
    salida = io.BytesIO()
    img.save(salida, format='PNG', optimize=True)
    return ContentFile(salida.getvalue())


class Command(BaseCommand):
    help = 'Crea usuarios de prueba y datos de ejemplo'

    def handle(self, *args, **options):
        biblio, creado = User.objects.get_or_create(username='bibliotecario', defaults={'email': 'biblio@example.com', 'is_staff': True})
        if creado:
            biblio.set_password('Biblio2026!')
            biblio.save()
        socios = []
        for nombre in ['socio', 'lucia', 'marcos']:
            u, creado = User.objects.get_or_create(username=nombre, defaults={'email': f'{nombre}@example.com'})
            if creado:
                u.set_password('Socio2026!')
                u.save()
            socios.append(u)
        if not User.objects.filter(is_superuser=True).exists():
            User.objects.create_superuser('admin', 'admin@example.com', 'Admin2026!')

        if Book.objects.exists():
            self.stdout.write('Ya hay libros: no se crean datos de ejemplo.')
            return

        rnd = random.Random(7)
        hoy = timezone.localdate()
        for i, (titulo, autor, genero, anio, isbn) in enumerate(LIBROS):
            a, _ = Author.objects.get_or_create(name=autor)
            g, _ = Genre.objects.get_or_create(name=genero)
            libro = Book.objects.create(title=titulo, genre=g, year=anio, isbn=isbn, copies=rnd.choice([1, 1, 2, 3]),
                                        description=f'«{titulo}» ({anio}), de {autor}.')
            libro.authors.add(a)
            libro.cover.save(f'{isbn}.png', generar_portada(titulo, autor, i), save=True)

            # Historial: préstamos ya devueltos y reseñas de quienes lo leyeron
            lectores = rnd.sample(socios, rnd.randint(0, 3))
            for socio in lectores:
                inicio = hoy - timedelta(days=rnd.randint(20, 120))
                Loan.objects.create(book=libro, user=socio, loan_date=inicio, due_date=inicio + timedelta(days=14),
                                    returned_at=inicio + timedelta(days=rnd.randint(5, 18)))
                if rnd.random() < 0.8:
                    Review.objects.create(book=libro, user=socio, rating=rnd.randint(3, 5), comment=rnd.choice(COMENTARIOS))

        # Préstamos activos (uno vencido) para el socio de prueba
        libros = list(Book.objects.order_by('?')[:3])
        Loan.objects.create(book=libros[0], user=socios[0], loan_date=hoy - timedelta(days=3), due_date=hoy + timedelta(days=11))
        Loan.objects.create(book=libros[1], user=socios[1], loan_date=hoy - timedelta(days=20), due_date=hoy - timedelta(days=6))
        Loan.objects.create(book=libros[2], user=socios[2], loan_date=hoy - timedelta(days=1), due_date=hoy + timedelta(days=13))
        self.stdout.write(self.style.SUCCESS('Datos de ejemplo creados. Usuarios: bibliotecario / socio / lucia / marcos / admin'))
