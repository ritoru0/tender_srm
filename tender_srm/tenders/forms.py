from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User, Organization

class CustomUserCreationForm(UserCreationForm):
    role = forms.ChoiceField(choices=[choice for choice in User.ROLE_CHOICES if choice[0] != 'Менеджер'], label="Роль")  
    email = forms.EmailField(required=True, label="Email")
    
    # Поля организации 
    name = forms.CharField(
        max_length=200, 
        required=False, 
        label="Название организации"
    )
    fio = forms.CharField(
        max_length=100, 
        required=False, 
        label="ФИО руководителя"
    )
    registration_number = forms.CharField(
        max_length=50, 
        required=False, 
        label="УНП"
    )
    org_type = forms.CharField(
        max_length=50, 
        required=False, 
        label="Тип организации"
    )
    address = forms.CharField(
        max_length=200, 
        required=False, 
        label="Адрес",
        widget=forms.Textarea(attrs={'rows': 2})
    )
    phone = forms.CharField(
        max_length=20, 
        required=False, 
        label="Телефон"
    )
    
    # Документы
    charter = forms.FileField(
        label="Устав (PDF)", 
        required=False,
        widget=forms.FileInput(attrs={'accept': '.pdf'})
    )
    inn = forms.FileField(
        label="Свидетельство ИНН (PDF)", 
        required=False,
        widget=forms.FileInput(attrs={'accept': '.pdf'})
    )
    ogrn = forms.FileField(
        label="Свидетельство ОГРН (PDF)", 
        required=False,
        widget=forms.FileInput(attrs={'accept': '.pdf'})
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'role', 'password1', 'password2')

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role')
        
        if role in ['Фирма', 'Поставщик']:
            required_fields = [
                'name', 'fio', 'registration_number', 
                'org_type', 'charter', 'inn', 'ogrn'
            ]
            
            for field in required_fields:
                if not cleaned_data.get(field):
                    self.add_error(field, f'Это поле обязательно для роли "{role}"')
        
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        
        if commit:
            user.save()
            
            if user.role in ['Фирма', 'Поставщик']:
                organization = Organization(
                    user=user,
                    name=self.cleaned_data['name'],
                    fio=self.cleaned_data['fio'],
                    registration_number=self.cleaned_data['registration_number'],
                    org_type=self.cleaned_data['org_type'],
                    address=self.cleaned_data['address'],
                    phone=self.cleaned_data['phone'],
                    description=f"Автоматически создана при регистрации {user.role}"
                )
                organization.save()
        
        return user
    
    