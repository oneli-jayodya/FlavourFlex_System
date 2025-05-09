from tkinter import Canvas
from django.contrib.auth.models import Group
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.hashers import make_password
from django.contrib.auth import login as auth_login, authenticate, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from webapp.models import Comment, DeletedAccount, FoodType, Ingredient, Method, RecipeIngredient, Recipes, UserRoleRequest
from django.db.models import Count
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Flowable, Table, TableStyle, HRFlowable
from reportlab.lib.units import inch
from datetime import datetime
from reportlab.graphics.shapes import Line,Drawing
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from django.utils.timezone import now, timedelta



def start(request):
    recipes = Recipes.objects.all()
    return render(request, 'startup.html', {
        'recipes': recipes
    })

def get_food_types(request):
    food_types = FoodType.objects.all().values('id', 'type')
    return JsonResponse(list(food_types), safe=False)


def get_methods(request):
    methods = Method.objects.all().values('id', 'name')
    return JsonResponse(list(methods), safe=False)


def get_ingredients(request):
    ingredients = Ingredient.objects.all().values('id', 'name')
    return JsonResponse(list(ingredients), safe=False)


def get_suggested_ingredients(request, have_ingredient_ids):
    try:
        have_ingredient_ids = [int(id) for id in have_ingredient_ids.split(',') if id]

        if not have_ingredient_ids:
            return JsonResponse({"error": "No valid ingredients found."}, status=400)

        suggested_ingredients = Ingredient.objects.filter(
            recipeingredient__recipe__recipeingredient__ingredient_id__in=have_ingredient_ids
        ).exclude(
            id__in=have_ingredient_ids
        ).annotate(
            usage_count=Count('recipeingredient__recipe')
        ).order_by('-usage_count')[:5]

        response = [{'id': ingredient.id, 'name': ingredient.name} for ingredient in suggested_ingredients]
        return JsonResponse(response, safe=False)

    except Exception as e:
        print("Error in get_suggested_ingredients:", str(e))
        return JsonResponse({"error": "An unexpected error occurred."}, status=500)


def get_recipes(request, food_type_id, have_ingredient_ids, method_id):
    try:
        # Convert the ingredient IDs into integers
        have_ingredient_ids = [int(id) for id in have_ingredient_ids.split(',') if id]

        # Return error if no valid ingredient IDs are passed
        if not have_ingredient_ids:
            return JsonResponse({"error": "No valid ingredients found."}, status=400)

        # Query for recipes that match the selected food type, method, and ingredients
        recipes = Recipes.objects.filter(
            food_type_id=food_type_id,
            recipeingredient__ingredient_id__in=have_ingredient_ids,  # Filter by selected ingredients
            method_id=method_id,
        ).annotate(
            match_count=Count('recipeingredient__ingredient_id')  # Count matched ingredients
        ).order_by('-match_count').distinct()

        # Prepare the response data
        response = {
            'recipes': [{'id': recipe.id, 'name': recipe.name} for recipe in recipes]
        }

        return JsonResponse(response, safe=False)

    except Exception as e:
        print("Error in get_recipes:", str(e))
        return JsonResponse({"error": "An unexpected error occurred."}, status=500)
    
# Registration view
def register(request):
    if request.method == 'POST':
        username = request.POST['username']
        email = request.POST['email']
        password = request.POST['password']
        confirm_password = request.POST['confirm_password']

        # Password confirmation check
        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return redirect('register')

        # Username and email uniqueness check
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return redirect('register')

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already registered.")
            return redirect('register')

        # Create the user
        user = User.objects.create(
            username=username,
            email=email,
            password=make_password(password),  # Hash the password
        )

        # Add the user to the "User" group
        user_group, created = Group.objects.get_or_create(name='User')
        user.groups.add(user_group)

        messages.success(request, "Registration successful! Please log in.")
        return redirect('login')

    # If GET request, render the registration page
    return render(request, 'registration.html')

def login(request):

    # Check if the user is already authenticated
    if request.user.is_authenticated:
        # Redirect to the session-stored URL or default to the dashboard
        return redirect(request.session.pop('redirect_to', '/dashboard'))

    if request.method == 'POST':
        username = request.POST['name']  # 'name' input field in login form
        password = request.POST['password']  # 'password' input field in login form

        # Authenticate the user
        user = authenticate(request, username=username, password=password)

        if user is not None:
            auth_login(request, user)  # Log the user in

            # Redirect to the session-stored URL or default to the dashboard
            return redirect(request.session.pop('redirect_to', '/dashboard'))
        else:
            messages.error(request, "Invalid username or password.")
            return redirect('login')  # Redirect back to login page for retry

    # Store the intended destination in the session if provided in GET request
    if 'redirect_to' in request.GET:
        request.session['redirect_to'] = request.GET['redirect_to']

    if 'next' in request.GET:
        request.session['redirect_to'] = request.GET['next']

    return render(request, 'login.html')  # Render login page for GET request

@login_required
def dash(request):
    user = request.user
    is_admin = user.groups.filter(name="Admin").exists()
    is_author = user.groups.filter(name="Author").exists()
    is_user = user.groups.filter(name="User").exists()
    data = get_filtered_counts("monthly")

# Only users who are in the 'User' group and not in 'Admin' or 'Author'
    users_count = User.objects.filter(groups__name='User', is_superuser=False, is_staff=False).count() if is_admin else 0
    recipes_count = Recipes.objects.count()  # Replace with actual count of recipes
    use_count = User.objects.filter(is_superuser=False, is_staff=False).count() if is_admin else 0
    author_group = Group.objects.get(name='Author')
    authors_count = author_group.user_set.count() if is_admin else 0
    # comments_count = Comment.objects.count() if is_admin else 0  # Total comments count
    request_count = UserRoleRequest.objects.filter(status='Pending').count()
    # Retrieve role request and author approval messages
    role_request_message = request.session.get('role_request_message', None)
    if role_request_message:
        del request.session['role_request_message']  # Clear the message from session after showing it

    author_approved_message = request.session.get(f'author_approved_message_{user.id}')
    if author_approved_message:
        del request.session[f'author_approved_message_{user.id}']  # Clear the message after showing

    if 'redirect_to' in request.GET:
        request.session['redirect_to'] = request.GET['redirect_to']
        
    context = {
        'is_admin': is_admin,
        'is_author': is_author,
        'is_user': is_user,
        'users_count': users_count,
        'recipes_count': recipes_count,
        'authors_count': authors_count,
        'role_request_message': role_request_message,  
        'role_approval_message': author_approved_message,  
        'request_count': request_count, 
        'use_count':use_count,
        'data':data,
    }

    return render(request, 'dashboard.html', context)

@login_required
def generate_detailed_report(request):
    # Create PDF response
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="detailed_system_report.pdf"'

    doc = SimpleDocTemplate(response, pagesize=A4)
    elements = []

    # Styles
    styles = getSampleStyleSheet()
    
    # Custom header style
    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Title'],
        fontSize=24,
        textColor=colors.HexColor("#FB8F4D"),
        spaceAfter=12,
        alignment=0,
    )

    # "Flavour" and "Flex" with distinct colors
    flavour_text = '<font color="#FB8F4D"><b>Flavour</b></font>'
    flex_text = '<font color="#FFD700"><b>Flex</b></font>'
    
    header_paragraph = Paragraph(f"{flavour_text}{flex_text}", header_style)
    elements.append(header_paragraph)
    
    elements.append(ColorLine(colors.green, width=500))

    elements.append(Spacer(1, 20))

    elements.append(Paragraph("Registration Detailed Report", styles['Heading2']))

    # Fetch all users except Admins (is_superuser=False)
    users = User.objects.filter(is_superuser=False).distinct().order_by('date_joined')

    # Count Users and Authors for Pie Chart
    total_authors = users.filter(groups__name="Author").count()
    total_users = users.count() - total_authors  # Remaining users are general users

    elements.append(Spacer(1, 30))
    
    # Pie Chart Visualization
    if total_users > 0 or total_authors > 0:
        drawing = Drawing(300, 150)
        pie = Pie()
        pie.x = 65
        pie.y = 10
        pie.width = 150
        pie.height = 150
        pie.data = [total_users, total_authors]
        pie.labels = ["Users", "Authors"]
        pie.slices[0].fillColor = colors.HexColor("#4CAF50")  # Green for Users
        pie.slices[1].fillColor = colors.HexColor("#FB8F4D")  # Orange for Authors
        drawing.add(pie)
        elements.append(Paragraph("User vs Authors Distribution ", styles['Heading2']))
        elements.append(Spacer(1, 20))
        elements.append(drawing)

    # User Table (Includes both Users and Authors)
    elements.append(Spacer(1, 30))
    elements.append(Paragraph("Registered Users & Authors:", styles['Heading2']))
    user_data = [["Username", "Email", "User Type", "Date Joined"]]

    for user in users:
        user_type = "Author" if user.groups.filter(name="Author").exists() else "User"
        date_joined = user.date_joined.strftime("%Y-%m-%d") if user.date_joined else "N/A"
        user_data.append([user.username, user.email, user_type, date_joined])
    
    user_table = Table(user_data)
    user_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
    ]))
    elements.append(user_table)

    # Footer with Download Date
    download_date = datetime.now().strftime("%B %d, %Y %I:%M %p")
    footer_style = ParagraphStyle(
        'FooterStyle',
        fontSize=10,
        textColor=colors.grey,
        alignment=2,  # Right-aligned
        spaceBefore=30,
    )
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"Downloaded on: {download_date}", footer_style))

    # Build the PDF
    doc.build(elements)

    return response

def get_filtered_counts(time_range):
    """ Returns the count of authors and recipes based on the selected time range """
    today = now().date()

    if time_range == "daily":
        start_date = today
    elif time_range == "weekly":
        start_date = today - timedelta(days=7)
    elif time_range == "monthly":
        start_date = today.replace(day=1)  # Start of the month
    else:
        return {"authors_count": 0, "recipes_count": 0}

    # Exclude Admin users
    admin_group = Group.objects.get(name="Admin")
    admin_users = admin_group.user_set.all()
    
    # Filter users and authors
    users = User.objects.filter(is_superuser=False).exclude(id__in=admin_users)
    author_group = Group.objects.get(name="Author")
    authors = users.filter(groups=author_group, date_joined__date__gte=start_date)
    
    # Filter recipes based on creation date
    recipes = Recipes.objects.filter(created_at__date__gte=start_date)

    return {
        "authors_count": authors.count(),
        "recipes_count": recipes.count(),
    }

def dashboard_view(request):
    # Default: show monthly stats when page loads
    data = get_filtered_counts("monthly")

    return render(request, 'dashboard.html', data)

@login_required
def generate_author_report(request):
    # Create PDF response
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="author_report.pdf"'

    doc = SimpleDocTemplate(response, pagesize=A4)
    elements = []

    # Styles
    styles = getSampleStyleSheet()
    
    # Custom header style for FlavourFlex
    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Title'],
        fontSize=24,
        textColor=colors.HexColor("#FB8F4D"),
        spaceAfter=12,
        alignment=0,
    )

    # Header text
    header_paragraph = Paragraph('<font color="#FB8F4D"><b>Flavour</b></font>' 
                                 '<font color="#FFD700"><b>Flex</b></font>', header_style)
    elements.append(header_paragraph)

    elements.append(ColorLine(colors.green, width=500))

    elements.append(Spacer(1, 30))

    # Decorative separator
    elements.append(Paragraph("Author Report", styles['Heading2']))

    elements.append(Spacer(1, 20))
    # Fetch Authors and count their recipes and comments
    authors = User.objects.filter(groups__name='Author').order_by('date_joined')
    
    # Prepare data for the table (Author, Recipe Count, Comment Count)
    author_data = []
    for author in authors:
        recipe_count = Recipes.objects.filter(author=author).count()
        comment_count = Comment.objects.filter(recipe__author=author).count()  # Assuming Comments are linked to Recipes
        author_data.append([author.username, recipe_count, comment_count])

    # Table data (including headers)
    author_table_data = [["Author Username", "Recipe Count", "Comment Count"]]
    author_table_data.extend(author_data)

    # Create the table
    author_table = Table(author_table_data)
    author_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    elements.append(author_table)

    # Build PDF
    doc.build(elements)

    return response


def get_chart_data(request):
    """ AJAX request handler to get pie chart data based on selected time range """
    time_range = request.GET.get('range', 'monthly')  # Default to 'monthly'
    data = get_filtered_counts(time_range)
    return JsonResponse(data)

@login_required
def profile_view(request):
    user = request.user
    is_admin = user.groups.filter(name="Admin").exists()
    is_author = user.groups.filter(name="Author").exists()
    is_user = user.groups.filter(name="User").exists()
    return render(request, "profile.html", {"user": request.user,'is_admin': is_admin,
        'is_author': is_author,
        'is_user': is_user})

@login_required
def change_password(request):
    user = request.user
    is_admin = user.groups.filter(name="Admin").exists()
    is_author = user.groups.filter(name="Author").exists()
    is_user = user.groups.filter(name="User").exists()
    if request.method == "POST":
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Prevent logout after password change
            messages.success(request, "Your password was successfully updated!")
            return redirect("profile")  # Redirect to profile page
    else:
        form = PasswordChangeForm(user=request.user)

    return render(request, "change_password.html", {"form": form,'is_admin': is_admin,
        'is_author': is_author,
        'is_user': is_user})

@login_required
def delete_account(request):
    user = request.user
    is_admin = user.groups.filter(name="Admin").exists()
    is_author = user.groups.filter(name="Author").exists()
    is_user = user.groups.filter(name="User").exists()
    if request.method == 'POST':
        user = request.user
        # Save user details in DeletedAccount table
        DeletedAccount.objects.create(
            username=user.username,
            email=user.email,
        )
        
        # Remove the user from all groups
        user.groups.clear()
        
        # Delete the user
        user.delete()
        
        # Log out the user and redirect to a confirmation page or home
        messages.success(request, "Your account has been successfully deleted.")
        return redirect('home')  # Redirect to home or another page after deletion

    return render(request, 'delete_account.html',{'is_admin': is_admin,
        'is_author': is_author,
        'is_user': is_user})

# Logout view (optional)
def logout(request):
    if request.user.is_authenticated:
        auth_logout(request)
    #     logout(request)
    # request.session.flush() 
    return redirect('start')



@login_required
def request_author_role(request):
    user = request.user
    is_admin = user.groups.filter(name="Admin").exists()
    is_author = user.groups.filter(name="Author").exists()
    is_user = user.groups.filter(name="User").exists()

    comment_count = Comment.objects.filter(user=user).count()

    if request.method == 'POST':
        # Check if there's an existing request
        existing_request = UserRoleRequest.objects.filter(user=request.user).first()

        if existing_request:
            if existing_request.status == 'Denied':
                # If the request was denied, allow resubmission by resetting the status
                existing_request.status = 'Pending'
                existing_request.save()
                request.session['role_request_message'] = 'Your request has been resubmitted successfully.'
            else:
                request.session['role_request_message'] = 'You have already submitted a request.'
        else:
            # Create a new request if none exists
            UserRoleRequest.objects.create(user=request.user, requested_role='Author')
            request.session['role_request_message'] = 'Your request has been submitted successfully.'

        return redirect('dash')  # Redirect to the dashboard
    return render(request, 'request_role.html',{'is_admin': is_admin,'is_author': is_author,'is_user': is_user, 'comment_count': comment_count})

@login_required  
def manage_roles(request):  
    user = request.user  
    is_admin = user.groups.filter(name="Admin").exists()  

    # Retrieve all pending role requests to display in the table  
    requests = UserRoleRequest.objects.filter(status='Pending')  
    pending_requests_count = requests.count()  # Get the count of pending requests
    user_comment_counts = Comment.objects.values('user').annotate(comment_count=Count('id'))
    
    # Convert QuerySet to dictionary with User objects as keys
    comment_count_dict = {entry['user']: entry['comment_count'] for entry in user_comment_counts}

    if request.method == 'POST':  
        action = request.POST.get('action')  
        request_id = request.POST.get('request_id')  
        role_request = get_object_or_404(UserRoleRequest, id=request_id)  

        if action == 'approve':  
            role_request.status = 'Approved'  
            role_request.save()  

            # Add user to the "Author" group  
            author_group, _ = Group.objects.get_or_create(name='Author')  
            role_request.user.groups.add(author_group)  

            # Remove user from the "User" group  
            user_group = Group.objects.filter(name='User').first()  
            if user_group:  
                role_request.user.groups.remove(user_group)  
                
            request.session['role_request_message'] = f"Role request for {role_request.user.username} has been approved successfully."  

        elif action == 'deny':  
            role_request.status = 'Denied'  
            role_request.save()  
            
            request.session['role_request_message'] = f"Role request for {role_request.user.username} has been denied."  

        return redirect('dash')  

    return render(request, 'manage_request.html', {
        'is_admin': is_admin,  
        'requests': requests,  
        'pending_requests_count': pending_requests_count,  # Pass count to template
        'comment_count_dict': comment_count_dict
    })


@csrf_exempt
def add_food_type(request):
    if request.method == "POST":
        type_name = request.POST.get('type', '').strip()
        description = request.POST.get('description', '').strip()

        if not type_name:
            return JsonResponse({'success': False, 'error': 'Food type name cannot be empty.'})

        if FoodType.objects.filter(type=type_name).exists():
            return JsonResponse({'success': False, 'error': 'Food type already exists.'})

        try:
            food_type = FoodType.objects.create(type=type_name, description=description)
            return JsonResponse({'success': True, 'food_type_id': food_type.id, 'food_type_name': food_type.type})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Invalid request method.'})

@csrf_exempt
def add_ingredient(request):
    if request.method == "POST":
        ingredient_name = request.POST.get('ingredient_name', '').strip()

        if not ingredient_name:
            return JsonResponse({'success': False, 'error': 'Ingredient name cannot be empty.'})

        if Ingredient.objects.filter(name=ingredient_name).exists():
            return JsonResponse({'success': False, 'error': 'Ingredient already exists.'})

        try:
            ingredient = Ingredient.objects.create(name=ingredient_name)
            return JsonResponse({'success': True, 'ingredient_id': ingredient.id, 'ingredient_name': ingredient.name})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Invalid request method.'})

@csrf_exempt
def add_method(request):
    if request.method == "POST":
        method_name = request.POST.get('method_name', '').strip()

        if not method_name:
            return JsonResponse({'success': False, 'error': 'Method name cannot be empty.'})

        if Method.objects.filter(name=method_name).exists():
            return JsonResponse({'success': False, 'error': 'Method already exists.'})

        try:
            method = Method.objects.create(name=method_name)
            return JsonResponse({
                'success': True,
                'method_id': method.id,
                'method_name': method.name
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Invalid request method.'})


@login_required
@csrf_exempt
def adding_recipe(request):
    user = request.user
    is_admin = user.groups.filter(name="Admin").exists()
    is_author = user.groups.filter(name="Author").exists()
    is_user = user.groups.filter(name="User").exists()

    # Fetch all options for the dropdowns
    food_types = FoodType.objects.all()
    ingredients = Ingredient.objects.all()
    methods = Method.objects.all()

    if request.method == 'GET':
            print("GET request received")

    if request.method == 'POST':
            print("POST request received")
            print("POST data:", request.POST)  # Check what data is being sent

    if request.method == 'POST':
        # Process form data
        name = request.POST.get('recipe_name')
        description = request.POST.get('recipe_description')
        duration = request.POST.get('cooking_duration')
        food_type_id = request.POST.get('food_type')
        method_id = request.POST.get('cooking_method')
        selected_ingredients = request.POST.getlist('ingredients[]')

        print(f"Recipe Name: {name}, Description: {description}, Duration: {duration}")
        print(f"Food Type ID: {food_type_id}, Method ID: {method_id}")
        print(f"Selected Ingredients: {selected_ingredients}")

        # Validate and get food type and method
        try:
            food_type = FoodType.objects.get(id=food_type_id)
        except FoodType.DoesNotExist:
            food_type = None

        try:
            method = Method.objects.get(id=method_id)
        except Method.DoesNotExist:
            method = None

        # Ensure all required fields are provided
        if not all([name, description, duration, food_type, method]):
            return render(request, 'recipe_form.html', {
                'food_types': food_types,
                'ingredients': ingredients,
                'methods': methods,
                'is_admin': is_admin,
                'is_author': is_author,
                'is_user': is_user,
                'error': "All fields are required.",
            })

        try:
            # Create the recipe
            recipe = Recipes.objects.create(
                name=name,
                description=description,
                duration=duration,
                food_type=food_type,
                method=method,
                author=user
            )

            # Associate ingredients with the recipe
            for ingredient_id in selected_ingredients:
                ingredient = Ingredient.objects.get(id=ingredient_id)
                recipe.ingredients.add(ingredient)

            return redirect('recipe_list')  # Redirect to the recipe list
        except Exception as e:
            return render(request, 'recipe_form.html', {
                'food_types': food_types,
                'ingredients': ingredients,
                'methods': methods,
                'is_admin': is_admin,
                'is_author': is_author,
                'is_user': is_user,
                'error': f"Error creating recipe: {str(e)}",
            })

    # Render the recipe form
    return render(request, 'recipe_form.html', {
        'food_types': food_types,
        'ingredients': ingredients,
        'methods': methods,
        'is_admin': is_admin,
        'is_author': is_author,
        'is_user': is_user,
    })

def list_recipes(request):
    if not request.user.is_authenticated:
        return redirect(f'/login/?next={request.path}')
    
    user = request.user
    is_admin = user.groups.filter(name="Admin").exists()
    is_author = user.groups.filter(name="Author").exists()
    is_user = user.groups.filter(name="User").exists()

    # Get search parameters
    recipe_name = request.GET.get('recipe_name', '').strip()
    method_name = request.GET.get('method_name', '').strip()
    ingredient_name = request.GET.get('ingredient_name', '').strip()
    exclude_ingredient = request.GET.get('exclude_ingredient', '').strip()
    exclude_equipment = request.GET.get('exclude_equipment', '').strip()


    query = request.GET.get('q', '').strip()  # Combined search query
    show_all = request.GET.get('all') == 'true'  # Check if 'Show All Recipes' is clicked
    show_my_recipes = request.GET.get('my_recipes') == 'true'  # Check if 'Show My Recipes' is clicked

    recipe_id = request.GET.get('recipe_id')
    if recipe_id:
        # If recipe_id is present in the query params, show that recipe
        return redirect('recipe_detail', recipe_id=recipe_id)
    
    # Base query for recipes
    recipes = Recipes.objects.all()
    
    # Apply author-specific filter
    if is_author and show_my_recipes:
        recipes = recipes.filter(author=user)
    elif is_admin or is_user or show_all:
        recipes = Recipes.objects.all()
    else:
        recipes = Recipes.objects.filter(author=user)

    # Filter by recipe name
    if recipe_name:
        recipes = recipes.filter(name__icontains=recipe_name)

    # Filter by method name
    if method_name:
        recipes = recipes.filter(method__name__icontains=method_name)

    # Filter by ingredient name
    if ingredient_name:
        recipes = recipes.filter(ingredients__name__icontains=ingredient_name).distinct()
    
    # Exclude recipes containing the entered exclude_ingredient
    if exclude_ingredient:
        recipes = recipes.exclude(ingredients__name__icontains=exclude_ingredient).distinct()

    # If exclude_equipment is provided, exclude those equipment
    if exclude_equipment:
        recipes = recipes.exclude(method__name__icontains=exclude_equipment)

    # Combined query for general search
    if query:
        recipes = recipes.filter(
            Q(name__icontains=query) |
            Q(method__name__icontains=query) |
            Q(ingredients__name__icontains=query)
        ).distinct()

    # Pagination
    paginator = Paginator(recipes, 10)  # Show 10 recipes per page
    page = request.GET.get('page')
    try:
        recipes = paginator.page(page)
    except PageNotAnInteger:
        recipes = paginator.page(1)
    except EmptyPage:
        recipes = paginator.page(paginator.num_pages)

    for recipe in recipes:
        recipe.can_edit = is_admin or is_author

    food_types = FoodType.objects.all()

    return render(request, 'recipe.html', {
        'recipes': recipes,
        'food_types': food_types,
        'is_admin': is_admin,
        'is_author': is_author,
        'is_user': is_user,
        'query': query,
        'show_all': show_all,
        'show_my_recipes': show_my_recipes,
        'recipe_name': recipe_name,
        'method_name': method_name,
        'ingredient_name': ingredient_name,
        'exclude_ingredient': exclude_ingredient,
        'exclude_equipment':exclude_equipment,
    })

@login_required(login_url='/login/')
def recipe_detail(request, recipe_id):
    # Retrieve the recipe by its ID
    recipe = get_object_or_404(Recipes, id=recipe_id)
    return render(request, 'recipe_detail.html', {'recipe': recipe})

@login_required
@csrf_exempt
def edit_recipe(request, recipe_id):
    user = request.user
    is_admin = user.groups.filter(name="Admin").exists()
    is_author = user.groups.filter(name="Author").exists()

    # Fetch the recipe to edit
    recipe = get_object_or_404(Recipes, id=recipe_id)

    # Ensure the user is either the author of the recipe or an admin
    if not (is_admin or recipe.author == user):
        messages.error(request, "You do not have permission to edit this recipe.")
        return redirect('recipe_list')  # Redirect to recipe list page

    # Fetch options for the dropdowns (food types, ingredients, and methods)
    food_types = FoodType.objects.all()
    ingredients = Ingredient.objects.all()
    methods = Method.objects.all()

    # When the form is submitted (POST request)
    if request.method == 'POST':
        # Get the form data
        name = request.POST.get('recipe_name')
        description = request.POST.get('recipe_description')
        duration = request.POST.get('cooking_duration')
        food_type_id = request.POST.get('food_type')
        method_id = request.POST.get('cooking_method')
        selected_ingredients = request.POST.getlist('ingredients[]')

        # Validate and get the food type and method
        try:
            food_type = FoodType.objects.get(id=food_type_id)
        except FoodType.DoesNotExist:
            food_type = None

        try:
            method = Method.objects.get(id=method_id)
        except Method.DoesNotExist:
            method = None

        # Ensure all required fields are provided
        if not all([name, description, duration, food_type, method]):
            return render(request, 'recipe_form.html', {
                'food_types': food_types,
                'ingredients': ingredients,
                'methods': methods,
                'recipe': recipe,
                'is_admin': is_admin,
                'is_author': is_author,
                'error': "All fields are required.",
            })

        try:
            # Update the recipe
            recipe.name = name
            recipe.description = description
            recipe.duration = duration
            recipe.food_type = food_type
            recipe.method = method
            recipe.save()

            # Update the ingredients
            recipe.ingredients.clear()  # Remove existing ingredients
            for ingredient_id in selected_ingredients:
                ingredient = Ingredient.objects.get(id=ingredient_id)
                recipe.ingredients.add(ingredient)

            messages.success(request, "Recipe updated successfully!")
            return redirect('recipe_list')  # Redirect to the recipe list

        except Exception as e:
            return render(request, 'recipe_form.html', {
                'food_types': food_types,
                'ingredients': ingredients,
                'methods': methods,
                'recipe': recipe,
                'is_admin': is_admin,
                'is_author': is_author,
                'error': f"Error updating recipe: {str(e)}",
            })

    # Render the edit recipe form with prepopulated data
    return render(request, 'recipe_form.html', {
        'food_types': food_types,
        'ingredients': ingredients,
        'methods': methods,
        'recipe': recipe,  # Pass the recipe to the form for prepopulation
        'is_admin': is_admin,
        'is_author': is_author,
    })


def delete_recipe(request, recipe_id):
    user = request.user
    recipe = get_object_or_404(Recipes, id=recipe_id)

    if not (recipe.author == user):
        messages.error(request, "You do not have permission to delete this recipe.")
        return redirect('recipe_list')

    recipe.delete()
    messages.success(request, "Recipe deleted successfully.")
    return redirect('recipe_list')


# Custom class for colored horizontal lines
class ColorLine(Flowable):
    def __init__(self, color=colors.green, width=500):
        Flowable.__init__(self)
        self.color = color
        self.width = width

    def draw(self):
        self.canv.setStrokeColor(self.color)
        self.canv.setLineWidth(2)
        self.canv.line(0, 0, self.width, 0)

def download_recipe_pdf(request, recipe_id):
    # Fetch the recipe
    recipe = get_object_or_404(Recipes, id=recipe_id)

    # Create a PDF response
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{recipe.name}_recipe.pdf"'

    # Create the PDF object
    doc = SimpleDocTemplate(response, pagesize=A4)
    styles = getSampleStyleSheet()
    content = []

    # Custom header style for FlavourFlex logo
    header_style = ParagraphStyle(
        'HeaderStyle',
        fontSize=30,
        textColor=colors.HexColor("#FB8F4D"),
        alignment=0,  # Center alignment
        spaceAfter=20,
        leading=20,
    )
    
    # Add an outlined logo-style heading for "Flavour" and "Flex" with different colors
    flavour_text = '<font color="#FB8F4D"><b>Flavour</b></font>'
    flex_text = '<font color="#FFD700"><b>Flex</b></font>'
    
    outline_effect = (
        f'<b>{flavour_text}{flex_text}</b>'  # Black outline
    )

    content.append(Paragraph(outline_effect, header_style))

    # Add a paragraph for recipe encouragement text
    recipe_text = '<font color="#1a2f2f"><b>Enjoy our recipes</b></font>'
    content.append(Paragraph(recipe_text, getSampleStyleSheet()['Normal']))
    content.append(Spacer(1, 20))

    
    # Left-aligned heading
    header_style.alignment = 0  # Left alignment

    # decorative line immediately after the logo
    content.append(ColorLine(colors.green, width=500))

    # Recipe Name: Bold and Center
    recipe_name_style = ParagraphStyle(
        'RecipeNameStyle',
        fontSize=24,
        alignment=1,  # Center alignment
        leading=30,
        textColor=colors.black
    )
    content.append(Spacer(1, 40))
    content.append(Paragraph(f"<b>{recipe.name}</b>", recipe_name_style))
    content.append(Spacer(1, 40))  # Space after recipe name

    # Recipe Details: Big Font
    body_style = ParagraphStyle(
        'BodyStyle',
        fontSize=14,
        leading=20,
        spaceAfter=10
    )

    content.append(Paragraph(f"<b>Type:</b> {recipe.food_type.type}", body_style))
    content.append(Paragraph(f"<b>Description:</b> {recipe.description}", body_style))
    content.append(Paragraph(f"<b>Preparation Time:</b> {recipe.duration}", body_style))
    content.append(Paragraph(f"<b>Equipment:</b> {recipe.method.name}", body_style))
    content.append(Paragraph(f"<b>Ingredients:</b> {', '.join([ingredient.name for ingredient in recipe.ingredients.all()])}", body_style))
    
    # Add a decorative line at the end
    content.append(Spacer(1, 12))
    content.append(Paragraph('<hr/>', styles['Normal']))

    # Footer: Downloaded date in the right corner
    download_date = datetime.now().strftime("%B %d, %Y %I:%M %p")
    footer_style = ParagraphStyle(
        'FooterStyle',
        fontSize=10,
        textColor=colors.grey,
        alignment=2,  # Right-aligned
        spaceBefore=30,
    )
    content.append(Spacer(1, 12))
    content.append(Paragraph(f"Downloaded on: {download_date}", footer_style))

    # Build the PDF
    doc.build(content)

    return response

@login_required
def add_comment(request, recipe_id):
    recipe = get_object_or_404(Recipes, id=recipe_id)
    user = request.user

    # Check user roles
    is_admin = user.groups.filter(name="Admin").exists()
    is_author = user.groups.filter(name="Author").exists()
    is_user = user.groups.filter(name="User").exists()

    # Only allow users in the "User" group to add comments
    if not is_user:
        messages.error(request, "Only regular users can add comments.")
        return redirect('list_recipes')

    # Handle POST request for adding a comment
    if request.method == 'POST':
        comment_text = request.POST.get('comment')
        if comment_text:
            Comment.objects.create(recipe=recipe, user=user, text=comment_text)
            messages.success(request, "Comment added successfully!")
            return redirect('add_comment', recipe_id=recipe.id)

    # Fetch only comments by the logged-in user for display
    comments = recipe.comments.filter(user=user)

    # Render the template
    return render(request, 'add_comment.html', {
        'recipe': recipe,
        'comments': comments,
        'is_user': is_user,  # This ensures we can conditionally show content in the template
    })

@login_required
def show_comments(request, recipe_id):
    user = request.user
    is_admin = user.groups.filter(name="Admin").exists()
    is_author = user.groups.filter(name="Author").exists()
    is_user = user.groups.filter(name="User").exists()
    # Fetch the recipe object by its ID
    recipe = get_object_or_404(Recipes, id=recipe_id)

    # Filter comments related to the specific recipe
    comments = recipe.comments.all()  # Use the related_name defined in the Comment model

    return render(request, 'show_comments.html', {
        'recipe': recipe,
        'comments': comments,'is_admin': is_admin,'is_author': is_author,'is_user': is_user
    })

@login_required
def edit_comment(request, recipe_id, comment_id):
    user = request.user
    is_admin = user.groups.filter(name="Admin").exists()
    is_author = user.groups.filter(name="Author").exists()
    is_user = user.groups.filter(name="User").exists()
    comment = get_object_or_404(Comment, id=comment_id, user=request.user)
    if request.method == 'POST':
        comment_text = request.POST.get('comment')
        if comment_text:
            comment.text = comment_text
            comment.save()
        return redirect('show_comments', recipe_id=recipe_id)
    return render(request, 'edit_comment.html', {'comment': comment, 'is_admin': is_admin,'is_author': is_author,'is_user': is_user})

@login_required
def delete_comment(request, recipe_id, comment_id):
    user = request.user
    is_admin = user.groups.filter(name="Admin").exists()
    is_author = user.groups.filter(name="Author").exists()
    is_user = user.groups.filter(name="User").exists()
    comment = get_object_or_404(Comment, id=comment_id, user=request.user)
    if request.method == 'POST':
        comment.delete()
        return redirect('show_comments', recipe_id=recipe_id)
    return render(request, 'delete_comment.html', {'comment': comment,'is_admin': is_admin,'is_author': is_author,'is_user': is_user})

def report_page(request):
    user = request.user
    is_admin = user.groups.filter(name="Admin").exists()
    is_author = user.groups.filter(name="Author").exists()
    is_user = user.groups.filter(name="User").exists()

    methods = Method.objects.all()
    recipe = Recipes.objects.values_list('method', flat=True).distinct()
    return render(request, 'report.html', {'methods': methods, 'recipe': recipe, 'is_admin': is_admin,'is_author': is_author,'is_user': is_user})


def generate_pdf(request):
    if request.method == 'POST':
        method_id = request.POST.get('method')
        method = get_object_or_404(Method, id=method_id)
        recipes = Recipes.objects.filter(method=method)
        recipe_count = recipes.count() 

        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="Report_{method.name}.pdf"'

        doc = SimpleDocTemplate(response, pagesize=A4)
        styles = getSampleStyleSheet()
        content = []

        # Logo Title
        header_style = ParagraphStyle(
            'HeaderStyle',
            fontSize=26,
            textColor=colors.HexColor("#FB8F4D"),
            alignment=0,  # Center alignment
            spaceAfter=20,
            leading=10,
        )
        flavour_text = '<font color="#FB8F4D"><b>Flavour</b></font>'
        flex_text = '<font color="#FFD700"><b>Flex</b></font>'
        content.append(Paragraph(f"{flavour_text}{flex_text}", header_style))

        content.append(ColorLine(colors.green, width=500))
        content.append(Spacer(1, 30))

        # Method Name
        method_style = ParagraphStyle('MethodStyle', fontSize=18, textColor=colors.black, alignment=1)
        content.append(Paragraph(f"<b>Equipments:</b> {method.name}", method_style))
        content.append(Spacer(1, 25))

        # Recipe Count
        count_style = ParagraphStyle('CountStyle', fontSize=14, textColor=colors.blue, alignment=1)
        content.append(Paragraph(f"<b>Total Recipes:</b> {recipe_count}", count_style))
        content.append(Spacer(1, 15))

        # Recipes List
        body_style = ParagraphStyle('BodyStyle', fontSize=14, leading=20, spaceAfter=10)
        if recipes:
            for recipe in recipes:
                content.append(Paragraph(f"• {recipe.name}", body_style))
        else:
            content.append(Paragraph("No recipes found for this method.", body_style))

        content.append(Spacer(1, 40))
        # Subtitle with Date
        date_style = ParagraphStyle('DateStyle', fontSize=12, textColor=colors.grey, alignment=1)
        current_date = datetime.now().strftime("%B %d, %Y")
        content.append(Paragraph(f"Generated on: {current_date}", date_style))

        doc.build(content)
        return response

    return HttpResponse("Invalid Request")

def generate_ingre(request):
        
    if request.method == 'POST':
        recipe_name = request.POST.get('recipe_name')

        # Get all recipe versions containing the entered name
        recipes = Recipes.objects.filter(name__icontains=recipe_name)

        if not recipes.exists():
            return HttpResponse("No recipes found for the entered name.")

        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{recipe_name}_Report.pdf"'

        doc = SimpleDocTemplate(response, pagesize=A4)
        styles = getSampleStyleSheet()
        content = []

        # Header with Logo
        header_style = ParagraphStyle('HeaderStyle', fontSize=26, textColor=colors.HexColor("#FB8F4D"), alignment=0, spaceAfter=20,)
        flavour_text = '<font color="#FB8F4D"><b>Flavour</b></font>'
        flex_text = '<font color="#FFD700"><b>Flex</b></font>'
        content.append(Paragraph(f"{flavour_text}{flex_text}", header_style))

        content.append(ColorLine(colors.green, width=500))
        content.append(Spacer(1, 30))

        
        # Recipe Name
        recipe_style = ParagraphStyle('RecipeStyle', fontSize=18, textColor=colors.black, alignment=1)
        content.append(Paragraph(f"<b>Recipe Report for:</b> {recipe_name}", recipe_style))
        content.append(Spacer(1, 25))

        # Grouping recipes by author
        recipe_data = []
        ingredient_counts = []
        authors = []

        for recipe in recipes:
            author_name = recipe.author.username  # Assuming `author` is a ForeignKey to `User`
            ingredient_count = recipe.ingredients.count()
            recipe_data.append([f"{recipe.name}", ingredient_count])
            authors.append(f"{author_name}'s {recipe.name}")
            ingredient_counts.append(ingredient_count)

        # Create a Table
        table_data = [["Recipe Version", "Ingredient Count"]] + recipe_data

        table = Table(table_data, colWidths=[250, 150])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#FB8F4D")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))

        content.append(table)
        content.append(Spacer(1, 20))

        # Generate Bar Chart
        drawing = Drawing(400, 200)
        bar_chart = VerticalBarChart()
        bar_chart.x = 50
        bar_chart.y = 20
        bar_chart.height = 150
        bar_chart.width = 300
        bar_chart.data = [ingredient_counts]
        bar_chart.categoryAxis.categoryNames = authors
        bar_chart.valueAxis.valueMin = 0
        bar_chart.valueAxis.valueMax = max(ingredient_counts) + 2  # Adjust max value
        bar_chart.bars[0].fillColor = colors.HexColor("#FB8F4D")

        drawing.add(bar_chart)
        content.append(drawing)

        content.append(Spacer(1, 40))

        # Subtitle with Date
        date_style = ParagraphStyle('DateStyle', fontSize=12, textColor=colors.grey, alignment=2)
        download_date = datetime.now().strftime("%B %d, %Y %I:%M %p")
        content.append(Paragraph(f"Generated on: {download_date}", date_style))
        

        doc.build(content)
        return response

    return HttpResponse("Invalid Request")