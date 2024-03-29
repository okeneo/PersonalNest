from account.models import UserProfile
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.validators import UnicodeUsernameValidator
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class UserRegisterSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(max_length=255, required=True)
    username = serializers.CharField(max_length=150, required=True)
    password1 = serializers.CharField(
        style={"input_type": "password"}, required=True, write_only=True
    )
    password2 = serializers.CharField(
        style={"input_type": "password"}, required=True, write_only=True
    )

    class Meta:
        model = UserProfile
        fields = [
            "email",
            "username",
            "password1",
            "password2",
        ]

    def validate_email(self, email):
        email = email.lower()
        try:
            UserProfile.objects.get(email=email)
            # TODO: Check if the user has been unverified for more than 3 days? so that we can make the
            # 3 days more precise? keeping in mind the error time for a cron job. We could get to
            # delete such a user 3.05 days after for example, which is okay, but to maintain our
            # contract with this user we check so that we can allow their credentials to work as we
            # said it would after 3 days.
            raise serializers.ValidationError(f"The email address '{email}' is already registered.")
        except UserProfile.DoesNotExist:
            return email

    def validate_username(self, username):
        try:
            UserProfile.objects.get(username=username)
            # TODO: Check if the user has been unverified for more than 3 days? so that we can make the
            # 3 days more precise? keeping in mind the error time for a cron job. We could get to
            # delete such a user 3.05 days after for example, which is okay, but to maintain our
            # contract with this user we check so that we can allow their credentials to work as we
            # said it would after 3 days.
            raise serializers.ValidationError(f"The username '{username}' is already registered.")
        except UserProfile.DoesNotExist:
            username_validator = UnicodeUsernameValidator()
            try:
                # Validate the username using the default User model username validator.
                username_validator(username)
            except ValueError as e:
                raise serializers.ValidationError(str(e))
            return username

    def validate_password1(self, password1):
        try:
            # Validate the password using Django's built-in password validator.
            validate_password(password1)
        except ValueError as e:
            raise serializers.ValidationError(str(e))
        return password1

    def validate(self, data):
        password1 = data.get("password1")
        password2 = data.get("password2")

        if password1 != password2:
            raise serializers.ValidationError("Passwords do not match.")

        return data

    def create(self, validated_data):
        email = validated_data.get("email")
        username = validated_data.get("username")
        password = validated_data.get("password1")

        user = UserProfile(email=email, username=username)
        user.set_password(password)

        # A user must verify their email before they are set to active.
        user.is_active = False
        user.save()

        return user


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """A custom serializer that adds 'username' to the payload of a JWT token."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["username"] = user.username
        return token


class UserProfilePublicSerializer(serializers.ModelSerializer):
    """The fields in this serializer represent data that can be viewed by anyone on the
    internet."""

    class Meta:
        model = UserProfile
        fields = [
            "username",
            "bio",
        ]


class UserProfilePrivateSerializer(serializers.ModelSerializer):
    """The fields in this serializer represent data that only the user of the associated
    account, or users with the admin role should have access to."""

    username = serializers.CharField(max_length=150, allow_blank=False)
    email = serializers.EmailField(read_only=True)
    bio = serializers.CharField(max_length=255, allow_blank=True)
    first_name = serializers.CharField(max_length=150, allow_blank=True)
    last_name = serializers.CharField(max_length=150, allow_blank=True)
    role = serializers.CharField(read_only=True)

    class Meta:
        model = UserProfile
        fields = [
            "username",
            "email",
            "bio",
            "first_name",
            "last_name",
            "role",
        ]

    def validate_username(self, username):
        try:
            UserProfile.objects.get(username=username)
            raise serializers.ValidationError(f"The username '{username}' is already registered.")
        except UserProfile.DoesNotExist:
            username_validator = UnicodeUsernameValidator()
            try:
                # Validate the username using the default User model username validator.
                username_validator(username)
            except ValueError as e:
                raise serializers.ValidationError(str(e))
            return username


class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        exclude = [
            "password",
        ]


class PasswordChangeSerializer(serializers.ModelSerializer):
    old_password = serializers.CharField(
        style={"input_type": "password"}, required=True, write_only=True
    )
    new_password1 = serializers.CharField(
        style={"input_type": "password"}, required=True, write_only=True
    )
    new_password2 = serializers.CharField(
        style={"input_type": "password"}, required=True, write_only=True
    )

    class Meta:
        model = UserProfile
        fields = [
            "old_password",
            "new_password1",
            "new_password2",
        ]

    def validate_old_password(self, old_password):
        user = self.context.get("user")
        if not user.check_password(old_password):
            raise serializers.ValidationError("Wrong password.")
        return old_password

    def validate_new_password1(self, new_password1):
        try:
            # Validate the password using Django's built-in password validator.
            validate_password(new_password1)
        except ValueError as e:
            raise serializers.ValidationError(str(e))
        return new_password1

    def validate(self, data):
        old_password = data.get("old_password")
        new_password1 = data.get("new_password1")
        new_password2 = data.get("new_password2")

        if old_password == new_password1:
            return serializers.ValidationError(
                "The new password must be different from the old password."
            )

        if new_password1 != new_password2:
            raise serializers.ValidationError("Passwords do not match.")

        return data


class PasswordResetSerializer(serializers.ModelSerializer):
    new_password1 = serializers.CharField(
        style={"input_type": "password"}, required=True, write_only=True
    )
    new_password2 = serializers.CharField(
        style={"input_type": "password"}, required=True, write_only=True
    )

    class Meta:
        model = UserProfile
        fields = [
            "new_password1",
            "new_password2",
        ]

    def validate_new_password1(self, new_password1):
        try:
            # Validate the password using Django's built-in password validator.
            validate_password(new_password1)
        except ValueError as e:
            raise serializers.ValidationError(str(e))
        return new_password1

    def validate(self, data):
        new_password1 = data.get("new_password1")
        new_password2 = data.get("new_password2")

        if new_password1 != new_password2:
            raise serializers.ValidationError("Passwords do not match.")

        return data
