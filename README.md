# Biblioteca Digital (Django)

Proyecto 2 del módulo de Django: **propuesta 8, Biblioteca Digital**. Gestión de préstamos y devoluciones de libros, con historial por socio y reseñas.

## Funcionalidades
**Obligatorias (según la propuesta)**
- **Préstamo y devolución** de libros. Préstamos de 14 días, máximo 3 activos por socio, control de ejemplares disponibles y bloqueo si el socio tiene algún préstamo vencido. Todo se valida en el servidor y dentro de una transacción.
- **Historial de préstamos por usuario** («Mis préstamos»: activos y devueltos, marcando los vencidos y las devoluciones con retraso).
- **Valoraciones y reseñas** (1-5 estrellas y comentario). Solo puede reseñar quien ha tenido el libro en préstamo, una vez por libro; se muestra la nota media en el catálogo.

**Extras**
- **Carga de portadas** (ImageField con Pillow, límite de 2 MB). Si un libro no tiene portada se genera una de color con el título.
- **Buscador avanzado**: título o ISBN, autor, género, rango de años, valoración mínima, solo disponibles, y orden por título, año, nota o número de préstamos.

**Además**
- Registro, login y logout, con dos roles:
  - **Bibliotecario** (`is_staff`): gestiona libros y autores, ve todos los préstamos (activos, vencidos y devueltos) y registra devoluciones.
  - **Socio** (rol por defecto al registrarse): pide prestado, devuelve los suyos y reseña.
- Catálogo público (se puede consultar sin cuenta).
- Fichas de autor con sus libros.
- Admin de Django configurado.
- 14 tests automatizados.

## Modelos
`Author` · `Genre` · `Book` (M2M con autores, FK a género, portada) · `Loan` (FK a libro y usuario; restricción: un préstamo activo por libro y socio) · `Review` (única por libro y socio) · `User` de Django.

## Puesta en marcha en local
```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py seed_demo         # usuarios, 16 libros con portada, préstamos y reseñas
python manage.py runserver
```

### Usuarios de prueba (los crea `seed_demo`)
| Usuario | Contraseña | Rol |
|---|---|---|
| `bibliotecario` | `Biblio2026!` | Bibliotecario |
| `socio` | `Socio2026!` | Socio (con un préstamo activo) |
| `lucia` | `Socio2026!` | Socio (con un préstamo **vencido**) |
| `admin` | `Admin2026!` | Superusuario (`/admin/`) |

## Tests
```bash
python manage.py test
```

## Despliegue en Render
Incluye `render.yaml` (servicio web) y `build.sh`. Como Render solo da una base PostgreSQL gratuita por cuenta, la demo usa SQLite (se migra y se cargan los datos de ejemplo en cada build); para usar PostgreSQL basta con definir `DATABASE_URL`.
1. Sube el proyecto a GitHub.
2. En Render: **New → Blueprint** y elige el repositorio.
3. Al terminar el build (migraciones y datos de ejemplo), la app queda en `https://<nombre>.onrender.com`.

Las portadas se guardan en el disco del servicio y se sirven con `SERVE_MEDIA=True`. En el plan gratuito de Render ese disco se borra en cada despliegue (las portadas de ejemplo se regeneran con `seed_demo`). En un proyecto real se usaría un almacenamiento externo (S3 o Cloudinary).

## Estructura
```
config/                    settings (variables de entorno), urls, wsgi
biblioteca/
  models.py                Author, Genre, Book, Loan (reglas de préstamo), Review
  views.py                 catálogo y buscador, préstamos, reseñas, gestión
  forms.py                 formularios y buscador avanzado
  templatetags/            filtro de estrellas
  context_processors.py    préstamos activos y vencidos en la navegación
  management/commands/seed_demo.py
  tests.py
templates/  static/css/app.css
```
