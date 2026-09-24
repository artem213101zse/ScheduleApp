from django.urls import path

from . import views

app_name = "journal"

urlpatterns = [
    path("", views.index, name="index"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("instruction/", views.instruction_view, name="instruction"),
    path("api/bootstrap/", views.api_bootstrap, name="api_bootstrap"),
    path("api/lessons/", views.api_lessons, name="api_lessons"),
    path("api/lessons/create/", views.api_lesson_create, name="api_lesson_create"),
    path("api/lessons/copy-week/", views.api_copy_week, name="api_copy_week"),
    path("api/lessons/<int:pk>/update/", views.api_lesson_update, name="api_lesson_update"),
    path("api/lessons/<int:pk>/delete/", views.api_lesson_delete, name="api_lesson_delete"),
    path("api/edit-mode/", views.api_edit_mode, name="api_edit_mode"),
]
