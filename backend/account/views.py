from django.core.exceptions import ValidationError
from django.db import transaction
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.views import TokenObtainPairView

from .controller import (
    send_verification_email,
    validate_email_token_key,
    validate_email_update_token_key,
    validate_new_email,
    validate_resend_verification_email_operation,
    validate_reset_password_token_key,
)
from .models import (
    UserProfile,
    VerificationEmailToken,
    VerificationEmailUpdateToken,
    VerificationResetPasswordToken,
)
from .permissions import IsAdminUser, IsOwner, ReadOnly
from .serializers import (
    AccountSerializer,
    CustomTokenObtainPairSerializer,
    PasswordChangeSerializer,
    PasswordResetSerializer,
    UserProfilePrivateSerializer,
    UserProfilePublicSerializer,
    UserRegisterSerializer,
)


class RegisterView(APIView):
    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "username": openapi.Schema(type=openapi.TYPE_STRING),
                "email": openapi.Schema(type=openapi.TYPE_STRING),
                "password1": openapi.Schema(type=openapi.TYPE_STRING),
                "password2": openapi.Schema(type=openapi.TYPE_STRING),
            },
            required=[
                "username",
                "email",
                "password1",
                "password2",
            ],
        ),
        responses={
            201: "Created",
            400: "Bad Request",
        },
    )
    def post(self, request, *args, **kwargs):
        """Create a new user and send them a verification email.

        is_active and is_email_verified are initially set to false to indicate incomplete
        registration.
        """
        serializer = UserRegisterSerializer(data=request.data)
        with transaction.atomic():
            if serializer.is_valid():
                user = serializer.save()

                token = VerificationEmailToken.objects.create(user=user)
                send_verification_email("registration", user.email, token.key)
                token.increment_send_attempts()

                return Response(
                    {"detail": "User created successfully. Email verification sent."},
                    status=status.HTTP_201_CREATED,
                )
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ResendVerificationEmailView(APIView):
    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "email": openapi.Schema(type=openapi.TYPE_STRING),
            },
            required=[
                "email",
            ],
        ),
        responses={
            204: "No Content",
            400: "Bad Request",
        },
    )
    def post(self, request, *args, **kwargs):
        """Resend a user another email to verify the email address on their newly created
        account."""
        email = request.data.get("email")

        try:
            token, user = validate_resend_verification_email_operation(email)
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            # Getting to this point means the token has not exceeded the maximum number of send
            # attempts, so we create a new token for another attempt.
            curr_send_attempts = token.send_attempts
            token.delete()
            token = VerificationEmailToken.objects.create(user=user)
            token.send_attempts = curr_send_attempts
            token.save(update_fields=["send_attempts"])

            send_verification_email("registration", token.user.email, token.key)
            token.increment_send_attempts()

            return Response(
                {"detail": "Email verification resent."},
                status=status.HTTP_204_NO_CONTENT,
            )


class VerifyEmailView(APIView):
    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                "token_key", openapi.IN_QUERY, description="Token Key", type=openapi.TYPE_STRING
            )
        ],
        responses={
            204: "No Content",
            400: "Bad Request",
        },
    )
    def post(self, request, *args, **kwargs):
        """Check the validity of the verification token to complete a new user's registration."""
        token_key = self.request.query_params.get("token_key")
        try:
            token = validate_email_token_key(token_key)
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # Complete user registration.
        user = token.user
        user.is_active = True
        user.is_email_verified = True
        user.save()

        # Delete the verification token once the user has been registered successfully.
        token.delete()

        return Response(
            {"detail": "User registration complete."}, status=status.HTTP_204_NO_CONTENT
        )


class EmailUpdateView(APIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "new_email": openapi.Schema(type=openapi.TYPE_STRING),
            },
            required=[
                "new_email",
            ],
        ),
        responses={
            204: "No Content",
            400: "Bad Request",
        },
    )
    def post(self, request, *args, **kwargs):
        """Update a user's email address by sending a verification link to their new email."""
        new_email = request.data.get("new_email")
        user = request.user

        try:
            new_email = validate_new_email(new_email, user)
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        token, created = VerificationEmailUpdateToken.objects.get_or_create(user=user)
        if created:
            token.new_email = new_email
            token.save()
        else:
            # If a VerificationEmailUpdateToken token already exists for this user, create a new one
            # to ensure we are always using a new UUID for the token key.
            token.delete()
            token = VerificationEmailUpdateToken.objects.create(user=user, new_email=new_email)

        send_verification_email("update_email", new_email, token.key)

        return Response(
            {"detail": "A verification email has been sent to update the email address."},
            status=status.HTTP_204_NO_CONTENT,
        )


class VerifyEmailUpdateView(APIView):
    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                "token_key", openapi.IN_QUERY, description="Token Key", type=openapi.TYPE_STRING
            )
        ],
        responses={
            204: "No Content",
            400: "Bad Request",
        },
    )
    def post(self, request, *args, **kwargs):
        """Check the validity of the verification token to update a user's new email address."""
        token_key = self.request.query_params.get("token_key")
        try:
            token = validate_email_update_token_key(token_key)
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # Re-check that the email has not been assigned to a different user before verification.
        if UserProfile.objects.filter(email=token.new_email).exists():
            return Response(
                {"error": f"The email address '{token.new_email}' is already registered."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Set new email.
        user = token.user
        user.email = token.new_email
        user.save()

        # Delete the verification token once the user has changed their email successfully.
        token.delete()

        return Response(
            {"detail": "Email updated successfully."}, status=status.HTTP_204_NO_CONTENT
        )


class ResetPasswordView(APIView):
    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "email": openapi.Schema(type=openapi.TYPE_STRING),
            },
            required=[
                "email",
            ],
        ),
        responses={
            204: "No Content",
            400: "Bad Request",
        },
    )
    def post(self, request, *args, **kwargs):
        """Reset the password on a user's account. This represents the 'forgot password'
        functionality"""
        email = request.data.get("email")
        user = get_object_or_404(UserProfile, email=email)

        # Prevent inactive users from accessing this endpoint.
        if not user.is_active and user.is_email_verified:
            return Response({"error": "Unauthroized access."}, status=status.HTTP_401_UNAUTHORIZED)

        token, created = VerificationResetPasswordToken.objects.get_or_create(user=user)
        if not created:
            # If a VerificationResetPasswordToken token already exists for this user, create a new
            # one to ensure we are always using a new UUID for the token key.
            token.delete()
            token = VerificationResetPasswordToken.objects.create(user=user)

        send_verification_email("reset_password", user.email, token.key)

        return Response({"detail": "Password reset email sent"}, status=status.HTTP_204_NO_CONTENT)


class VerifyResetPasswordView(APIView):
    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                "token_key", openapi.IN_QUERY, description="Token Key", type=openapi.TYPE_STRING
            )
        ],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "new_password1": openapi.Schema(type=openapi.TYPE_STRING),
                "new_password2": openapi.Schema(type=openapi.TYPE_STRING),
            },
            required=[
                "new_password1",
                "new_password2",
            ],
        ),
        responses={
            204: "No Content",
            400: "Bad Request",
        },
    )
    def post(self, request, *args, **kwargs):
        """Check the validity of the verification token to allow a user to reset their password."""
        token_key = self.request.query_params.get("token_key")
        try:
            token = validate_reset_password_token_key(token_key)
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        serializer = PasswordResetSerializer(data=request.data)
        if serializer.is_valid():
            new_password = serializer.validated_data.get("new_password1")
            user = token.user
            user.set_password(new_password)

            # Allow new users to verify their email address with this endpoint.
            if not user.is_active and not user.is_email_verified:
                user.is_active = True
                user.is_email_verified = True
                VerificationEmailToken.objects.filter(user=user).delete()
            user.save()

            # Delete the verification token once the user has reset their password successfully.
            token.delete()

            return Response(
                {"detail": "Password reset successfully."}, status=status.HTTP_204_NO_CONTENT
            )
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CustomTokenObtainPairView(TokenObtainPairView):
    """A custom view for user authentication using JWT."""

    serializer_class = CustomTokenObtainPairSerializer


class UserProfileView(APIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (ReadOnly | (IsAuthenticated & IsOwner),)

    @swagger_auto_schema(
        tags=["UserProfile"],
        manual_parameters=[
            openapi.Parameter(
                "username", openapi.IN_PATH, description="Username", type=openapi.TYPE_STRING
            ),
        ],
        responses={
            204: "No Content",
            400: "Bad Request",
        },
    )
    def get(self, request, username, *args, **kwargs):
        """Get a user's profile.

        The user must be logged in (authenticated) and must either be the owner of the account,
        or have the admin role in order to view private data.
        """
        user = get_object_or_404(UserProfile, username=username)

        if request.user.is_authenticated:
            ADMIN = UserProfile.ADMIN
            if request.user == user or request.user.role == ADMIN:
                serializer = UserProfilePrivateSerializer(user)
            else:
                # Use the public serializer for users that do not have the admin role.
                serializer = UserProfilePublicSerializer(user)
        else:
            # Use the public serializer for non-authenticated users.
            serializer = UserProfilePublicSerializer(user)

        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, username, *args, **kwargs):
        """Update the information of a user.

        The email address and role cannot be updated with this view.
        """
        user = get_object_or_404(UserProfile, username=username)
        serializer = UserProfilePrivateSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AccountView(APIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated & (IsOwner | IsAdminUser),)

    def get(self, request, username, *args, **kwargs):
        """Get the data of a given user."""
        user = get_object_or_404(UserProfile, username=username)

        # Only users with the admin role should be able to view the data provided in the
        # AccountSerializer.
        if user.role != UserProfile.ADMIN:
            return Response(
                {"detail": "You do not have the permission to view this resource."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = AccountSerializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, username, *args, **kwargs):
        """Delete a user."""
        user = get_object_or_404(UserProfile, username=username)
        user.delete()
        return Response({"detail": "User deleted successfully."}, status=status.HTTP_204_NO_CONTENT)


class PasswordChangeView(APIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        user = request.user
        serializer = PasswordChangeSerializer(data=request.data, context={"user": user})
        if serializer.is_valid():
            user.set_password(serializer.validated_data.get("new_password1"))
            user.save()
            return Response(
                {"detail", "Password changed successfully."},
                status=status.HTTP_204_NO_CONTENT,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
# class LogoutAllDevices(APIView):
#     authentication_classes = (JWTAuthentication,)
#     permission_classes = (IsAuthenticated,)

#     def post(self, request, username, *args, **kwargs):
#         """Invalidates all access and refresh tokens associated with a user which will require
#         the user to login (re-authenticate) again."""
#         user = get_object_or_404(UserProfile, username=username)
