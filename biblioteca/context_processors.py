def prestamos_usuario(request):
    """Préstamos activos y vencidos del socio, para la barra de navegación."""
    if not request.user.is_authenticated:
        return {}
    activos = request.user.loans.active()
    return {'my_active_loans': activos.count(), 'my_overdue_loans': activos.overdue().count()}
