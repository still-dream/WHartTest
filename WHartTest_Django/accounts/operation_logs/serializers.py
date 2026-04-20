from rest_framework import serializers
from .models import OperationLog


class OperationLogSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    
    class Meta:
        model = OperationLog
        fields = [
            'id',
            'user',
            'username',
            'user_email',
            'feature',
            'path',
            'method',
            'ip_address',
            'user_agent',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']
