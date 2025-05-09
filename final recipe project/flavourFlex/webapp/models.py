import datetime
from django.contrib.auth.models import Group
from django.contrib.auth.models import User
from django.db import models
from django.core.validators import RegexValidator, MinValueValidator
from django.utils.timezone import now


# Create your models here.
class Admin(models.Model):
    id = models.AutoField(primary_key=True)  # Explicitly define the auto-incrementing ID
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='admin_profile')
    contact_number = models.CharField(
        max_length=15,
        validators=[
            RegexValidator(
                regex=r'^\+?[1-9]\d{1,14}$',  # E.164 phone number format
                message='Contact number must be a valid phone number (e.g., +1234567890).'
            )
        ]
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Admin: {self.user.username}"


class Author(models.Model):
    id = models.AutoField(primary_key=True)  # Explicitly define the auto-incrementing ID
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='author_profile')
    description = models.TextField(
        null=True, 
        blank=True,
        validators=[
            RegexValidator(
                regex=r'^[a-zA-Z0-9\s,.-]*$',  # Alphanumeric, spaces, commas, periods, and hyphens
                message='Description contains invalid characters.'
            )
        ]
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Author: {self.user.username}"

class FoodType(models.Model):
    id = models.AutoField(primary_key=True)  # Auto-generated ID
    type = models.CharField(
        max_length=50, 
        unique=True,
        validators=[RegexValidator(regex=r'^[A-Za-z ]+$', message="Type should only contain letters and spaces.")],
        null=False,  # Ensures this field is not null
    )
    description = models.TextField(
        validators=[RegexValidator(regex=r'^[A-Za-z0-9., ]+$', message="Description can contain letters, numbers, commas, and periods.")],
        null=False,  # Ensures this field is not null
    )

    def __str__(self):
        return self.type


class Ingredient(models.Model):
    id = models.AutoField(primary_key=True)  # Auto-generated ID
    name = models.CharField(
        max_length=50, 
        unique=True,
        validators=[RegexValidator(regex=r'^[A-Za-z ]+$', message="Ingredient name should only contain letters and spaces.")],
        null=False,  # Ensures this field is not null
    )

    def __str__(self):
        return self.name

class Method(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


class Recipes(models.Model):
    id = models.AutoField(primary_key=True)  # Auto-generated ID
    author = models.ForeignKey(User, on_delete=models.CASCADE, null=False,  default=1)  # Link to User model as author
    name = models.CharField(
        max_length=100, 
        validators=[RegexValidator(regex=r"^[A-Za-z0-9\s']+$", message="Recipe name can only contain letters, numbers, and spaces.")],
        null=False,  # Ensures this field is not null
    )
    description = models.TextField(
        validators=[RegexValidator(regex=r'^[A-Za-z0-9.,!? ]+$', message="Description can contain letters, numbers, and punctuation.")],
        null=False,  # Ensures this field is not null
    )
    food_type = models.ForeignKey(FoodType, on_delete=models.CASCADE, null=False)  # Ensures non-null
    ingredients = models.ManyToManyField(Ingredient, through='RecipeIngredient')
    method = models.ForeignKey(Method, on_delete=models.CASCADE, null=False, default=1)  # Cooking method
    duration = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],  # Duration must be a positive integer (in minutes)
        help_text="Enter cooking duration in minutes.",
        default=1,
        null=False
    )
    created_at = models.DateTimeField(default=now)

    def __str__(self):
        return self.name


class RecipeIngredient(models.Model):
    id = models.AutoField(primary_key=True)  # Auto-generated ID
    recipe = models.ForeignKey(Recipes, on_delete=models.CASCADE, null=False)  # Ensures non-null
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE, null=False)  # Ensures non-null

    def __str__(self):
        return f"{self.recipe.name} - {self.ingredient.name}"


    
class UserRoleRequest(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    requested_role = models.CharField(
        max_length=50,
        validators=[
            RegexValidator(
                regex=r'^[a-zA-Z\s]*$',  # Letters and spaces only
                message='Requested role must contain only letters and spaces.'
            )
        ]
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('Pending', 'Pending'),
            ('Approved', 'Approved'),
            ('Denied', 'Denied'),
        ],
        default='Pending'
    )

    def __str__(self):
        return f"{self.user.username} - {self.requested_role} ({self.status})"

class Comment(models.Model):
    recipe = models.ForeignKey(Recipes, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.user.username} on {self.recipe.title}'
    
class DeletedAccount(models.Model):
    username = models.CharField(max_length=150)
    email = models.EmailField()
    deleted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Deleted Account: {self.username} ({self.deleted_at})"