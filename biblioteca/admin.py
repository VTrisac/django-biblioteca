from django.contrib import admin

from .models import Author, Book, Genre, Loan, Review


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    search_fields = ['name']


admin.site.register(Genre)


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ['title', 'isbn', 'genre', 'year', 'copies']
    list_filter = ['genre']
    search_fields = ['title', 'isbn', 'authors__name']
    filter_horizontal = ['authors']


@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = ['book', 'user', 'loan_date', 'due_date', 'returned_at']
    list_filter = ['returned_at', 'loan_date']
    search_fields = ['book__title', 'user__username']


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['book', 'user', 'rating', 'created_at']
