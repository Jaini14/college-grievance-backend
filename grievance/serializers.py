# serializers.py
from os import access
import token
from rest_framework import serializers
from .models import User, Grievance
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken

# ✅ REGISTER
class RegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = '__all__'
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def create(self, validated_data):
        password = validated_data.pop('password')
        
         # 🔥 FORCE ROLE DEFAULT if missing
        if not validated_data.get("role"):
            validated_data["role"] = "STUDENT"
            
        user = User(**validated_data)
        user.set_password(password)  # 🔐 hash password
        user.save()

        return user

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        email = data.get("email")
        password = data.get("password")

        # ✅ find user by email first
        user = User.objects.filter(email=email).first()

        if not user:
            raise serializers.ValidationError("User not found")

        # ✅ now authenticate using username
        user = authenticate(username=user.username, password=password)

        if not user:
            raise serializers.ValidationError("Invalid password")

        # ✅ generate JWT
        refresh = RefreshToken.for_user(user)
        
        return {
         "access": str(refresh.access_token),
          "refresh": str(refresh),
          "role": (user.role or "").upper(),
         "full_name": user.full_name or "",
          "email": user.email,
         "department": user.department or ""
        }
class FacultySerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "full_name",
            "email",
            "department",
            "specialization",
            "staff_function",
            # "resolution_image"
        ]
        
# ✅ GRIEVANCE
class GrievanceSerializer(serializers.ModelSerializer):
    submitted_by_name = serializers.CharField(source="submitted_by.full_name", read_only=True)
    assigned_to_name = serializers.CharField(source="assigned_to.full_name", read_only=True)

    class Meta:
        model = Grievance
        fields = "__all__"

