from django.urls import path
from . import views  # Import the views module from the current app

urlpatterns = [
    path('', views.start, name='start'),  # Home or startup page
    path('register/', views.register, name='register'),  # Registration page
    path('login/', views.login, name='login'),  # Login page
    path('dashboard/', views.dash, name='dash'),  # Dashboard page
    path('generate_detailed_report/', views.generate_detailed_report, name='generate_detailed_report'),
    path('logout/', views.logout, name='logout'),  # Dashboard page

    # recipe urls
    path('adding_recipe/', views.adding_recipe, name='adding_recipe'),
    path('add-food-type/', views.add_food_type, name='add_food_type'),
    path('add-ingredient/', views.add_ingredient, name='add_ingredient'),
    path('add-method/', views.add_method, name='add_method'),
    path('recipes/', views.list_recipes, name='list_recipes'),
    path('recipes/<int:recipe_id>/', views.recipe_detail, name='recipe_detail'),
    path('recipe_list/', views.list_recipes, name='recipe_list'),
    path('recipes/edit/<int:recipe_id>/', views.edit_recipe, name='edit_recipe'),
    path('recipes/delete/<int:recipe_id>/', views.delete_recipe, name='delete_recipe'),
    path('get_food_types/', views.get_food_types, name='get_food_types'),
    path('get_methods/', views.get_methods, name='get_methods'),
    path('get_ingredients/', views.get_ingredients, name='get_ingredients'),
    path('get_suggested_ingredients/<str:have_ingredient_ids>/', views.get_suggested_ingredients, name='get_suggested_ingredients'),
    path('get_recipes/<int:food_type_id>/<str:have_ingredient_ids>/<int:method_id>/', views.get_recipes, name='get_recipes'),

    path('recipe/<int:recipe_id>/add_comment/', views.add_comment, name='add_comment'),
    path('recipe/<int:recipe_id>/comments/', views.show_comments, name='show_comments'),
    path('recipe/<int:recipe_id>/edit_comment/<int:comment_id>/', views.edit_comment, name='edit_comment'),
    path('recipe/<int:recipe_id>/delete_comment/<int:comment_id>/', views.delete_comment, name='delete_comment'),

    path("profile/", views.profile_view, name="profile"),
    path("profile/change-password/", views.change_password, name="change_password"),
    path("profile/delete-account/", views.delete_account, name="delete_account"),
    
    path('request-author/', views.request_author_role, name='request_author_role'),
    path('manage-roles/', views.manage_roles, name='manage_roles'),

    path('reports/', views.report_page, name='report_page'),
    path('generate_pdf/', views.generate_pdf, name='generate_pdf'),
    path('generate_ingre/', views.generate_ingre, name='generate_ingre'),
    path('get-chart-data/', views.get_chart_data, name='get_chart_data'),
    path('generate_author_report/', views.generate_author_report, name='generate_author_report'),

]
