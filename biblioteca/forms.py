from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Author, Book, Genre, Review


class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ['username', 'email']


class BookForm(forms.ModelForm):
    class Meta:
        model = Book
        fields = ['title', 'authors', 'genre', 'isbn', 'year', 'copies', 'description', 'cover']
        widgets = {
            'authors': forms.SelectMultiple(attrs={'size': 6}),
            'description': forms.Textarea(attrs={'rows': 4}),
        }

    def clean_cover(self):
        portada = self.cleaned_data.get('cover')
        if portada and hasattr(portada, 'size') and portada.size > 2 * 1024 * 1024:
            raise forms.ValidationError('La portada no puede superar 2 MB.')
        return portada


class AuthorForm(forms.ModelForm):
    class Meta:
        model = Author
        fields = ['name', 'birth_year', 'bio']
        widgets = {'bio': forms.Textarea(attrs={'rows': 4})}


class ReviewForm(forms.ModelForm):
    rating = forms.TypedChoiceField(label='Valoración', coerce=int,
                                    choices=[(n, '★' * n + '☆' * (5 - n)) for n in range(5, 0, -1)])

    class Meta:
        model = Review
        fields = ['rating', 'comment']
        widgets = {'comment': forms.Textarea(attrs={'rows': 3, 'placeholder': '¿Qué te ha parecido?'})}


class BookSearchForm(forms.Form):
    """Buscador avanzado del catálogo."""

    ORDER_CHOICES = [('title', 'Título (A-Z)'), ('-year', 'Más recientes'), ('-avg_rating', 'Mejor valorados'),
                     ('-n_loans', 'Más prestados')]
    q = forms.CharField(label='Título o ISBN', required=False)
    author = forms.CharField(label='Autor', required=False)
    genre = forms.ModelChoiceField(label='Género', queryset=Genre.objects.all(), required=False, empty_label='Todos')
    year_from = forms.IntegerField(label='Desde el año', required=False, min_value=0)
    year_to = forms.IntegerField(label='Hasta el año', required=False, min_value=0)
    min_rating = forms.TypedChoiceField(label='Valoración mínima', required=False, coerce=int, empty_value=None,
                                        choices=[('', 'Cualquiera')] + [(n, f'{n}★ o más') for n in range(4, 0, -1)])
    available = forms.BooleanField(label='Solo disponibles', required=False)
    order = forms.ChoiceField(label='Ordenar por', choices=ORDER_CHOICES, required=False)
