from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path('', views.BookListView.as_view(), name='book_list'),
    path('libros/nuevo/', views.BookCreateView.as_view(), name='book_create'),
    path('libros/<int:pk>/', views.BookDetailView.as_view(), name='book_detail'),
    path('libros/<int:pk>/editar/', views.BookUpdateView.as_view(), name='book_update'),
    path('libros/<int:pk>/prestar/', views.borrow, name='borrow'),
    path('libros/<int:pk>/resena/', views.add_review, name='add_review'),
    path('resenas/<int:pk>/eliminar/', views.delete_review, name='delete_review'),

    path('autores/', views.AuthorListView.as_view(), name='author_list'),
    path('autores/nuevo/', views.AuthorCreateView.as_view(), name='author_create'),
    path('autores/<int:pk>/', views.AuthorDetailView.as_view(), name='author_detail'),
    path('autores/<int:pk>/editar/', views.AuthorUpdateView.as_view(), name='author_update'),

    path('mis-prestamos/', views.my_loans, name='my_loans'),
    path('prestamos/<int:pk>/devolver/', views.return_loan, name='return_loan'),
    path('gestion/prestamos/', views.LoanAdminListView.as_view(), name='loan_admin_list'),

    path('cuentas/login/', auth_views.LoginView.as_view(), name='login'),
    path('cuentas/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('cuentas/registro/', views.signup, name='signup'),
]
