from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from .models import (
    UserProfile,
    VerificationEmailToken,
    VerificationEmailUpdateToken,
    VerificationPasswordResetToken,
)
from .tasks import send_verification_email_task

# from django.urls import reverse
# verification_url = reverse("email_confimation")
EMAIL_TEMPLATES = {
    "registration": {
        "subject": "Verify your email address",
        "message": "http://localhost:8000/api/blog/verify-email/?token_key={token_key}",
    },
    "update_email": {
        "subject": "Email Update Verification",
        "message": "http://localhost:8000/api/blog/verify-email-update/?token_key={token_key}"
        + "\nIf you didn't change it, you should click this link to recover it.",
    },
    "reset_password": {
        "subject": "Reset Password",
        "message": "http://localhost:8000/blog/verify-reset-password/?token_key={token_key}"
        + "\nIf you didn't change it, you should click this link to recover it.",
    },
}


def send_verification_email(template, email, token_key):
    send_verification_email_task.delay(template, email, token_key)


def validate_email_token_key(token_key):
    try:
        token = VerificationEmailToken.objects.get(key=token_key)
    except VerificationEmailToken.DoesNotExist:
        raise ValidationError("Invalid verification token.")

    if token.is_expired:
        raise ValidationError("Token expired.")

    return token


def validate_email_update_token_key(token_key):
    try:
        token = VerificationEmailUpdateToken.objects.get(key=token_key)
    except VerificationEmailUpdateToken.DoesNotExist:
        raise ValidationError("Invalid verification token.")

    if token.is_expired:
        raise ValidationError("Token expired.")

    return token


def validate_reset_password_token_key(token_key):
    try:
        token = VerificationPasswordResetToken.objects.get(key=token_key)
    except VerificationPasswordResetToken.DoesNotExist:
        raise ValidationError("Invalid verification token.")

    if token.is_expired:
        raise ValidationError("Token expired.")

    return token


def validate_resend_verification_email_operation(email):
    """Given an unverified email, validate that the user should be resent a new
    verification email."""
    if not email:
        raise ValidationError("Email Required.")

    try:
        user = UserProfile.objects.get(email=email)
    except UserProfile.DoesNotExist:
        raise ValidationError("User not found.")

    if user.is_active:
        raise ValidationError("User already registered.")

    try:
        token = VerificationEmailToken.objects.get(user=user)
    except VerificationEmailToken.DoesNotExist:
        # A scenario where an inactive user tries to access this endpoint.
        # This is equivalent to not user.is_active and not user.is_email_verified because
        # there should always be a token for a user that is not active but are yet to
        # verify their email.
        raise ValidationError("Unauthorized access.")

    if token.has_exceeded_maximum_attempts:
        raise ValidationError("Exceeded maximum send attempts.")

    return token, user


def validate_new_email(new_email, user):
    MAX_LENGTH = 255

    if not new_email:
        raise ValidationError("New email required.")

    new_email = clean_email(new_email)

    if len(new_email) > MAX_LENGTH:
        raise ValidationError("The new email address is too long.")

    try:
        validate_email(new_email)
    except ValidationError as e:
        raise ValidationError(str(e))

    if user.email == new_email:
        raise ValidationError(
            "The new email address must be different from the current email address."
        )

    try:
        UserProfile.objects.get(email=new_email)
        raise ValidationError(f"The email address '{new_email}' is already registered.")
    except UserProfile.DoesNotExist:
        return new_email


def clean_email(email):
    cleaned_email = email.lstrip("\n\r ").rstrip("\n\r ")
    cleaned_email = cleaned_email.lower()
    return cleaned_email


def get_sentinel_user():
    return UserProfile.objects.get(username="deleted")


def handle_deleted_user_comments(user):
    leaf_comments = user.comments.filter(parent_comment__isnull=False)
    leaf_comments.delete()
    parent_comments = user.comments.filter(parent_comment__isnull=True)
    parent_comments.update(user=get_sentinel_user(), is_deleted=True, text="")
