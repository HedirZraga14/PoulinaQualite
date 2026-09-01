import secrets

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models


class UserManager(BaseUserManager):
    """Manager for the email-based User model."""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")

        user = self.model(email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superusers must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superusers must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


# ---------------------------------------------------------------------------
# Dimensions du schéma en flocons
# ---------------------------------------------------------------------------

class Sector(models.Model):
    """Dim_secteur — secteur d'activité (Agro, Alimentaire, Avicole…)."""
    name = models.CharField(max_length=150, unique=True)
    manager = models.OneToOneField(
        'User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='managed_sector',
    )

    def __str__(self):
        return self.name


class Branch(models.Model):
    """Dim_filiale — filiale rattachée à un secteur."""
    code = models.PositiveIntegerField(unique=True, null=True, blank=True)
    name = models.CharField(max_length=150)
    sector = models.ForeignKey(
        Sector,
        on_delete=models.PROTECT,
        related_name='branches',
    )
    laboratoire = models.ForeignKey(
        'Laboratoire',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='branches',
    )

    class Meta:
        unique_together = ('name', 'sector')

    def __str__(self):
        return f'{self.code or "—"} - {self.name} ({self.sector})'


class Laboratoire(models.Model):
    """Dim_laboratoire — laboratoire d'analyse."""
    name = models.CharField(max_length=150, unique=True)

    def __str__(self):
        return self.name


class DateDim(models.Model):
    """Dim_date — dimension temporelle (Mois / Trimestre / Année)."""
    mois = models.CharField(max_length=50)
    trimestre = models.CharField(max_length=20, blank=True)
    annee = models.CharField(max_length=20)

    class Meta:
        unique_together = ('mois', 'annee')
        ordering = ['annee', 'mois']

    def __str__(self):
        return f'{self.mois} {self.annee} ({self.trimestre or "—"})'

    @staticmethod
    def compute_trimestre(mois: str) -> str:
        """Calcule le trimestre à partir du nom du mois en français."""
        mois_lower = (mois or '').strip().lower()
        months_q1 = {'janvier', 'février', 'fevrier', 'mars'}
        months_q2 = {'avril', 'mai', 'juin'}
        months_q3 = {'juillet', 'août', 'aout', 'septembre'}
        # Le reste tombe en Q4
        if mois_lower in months_q1:
            return 'T1'
        if mois_lower in months_q2:
            return 'T2'
        if mois_lower in months_q3:
            return 'T3'
        return 'T4'


# ---------------------------------------------------------------------------
# Table de faits
# ---------------------------------------------------------------------------

def generate_random_evaluation_int():
    return 100000000 + secrets.randbelow(900000000)


class Evaluation(models.Model):
    """Fact_Evaluation — table de faits des évaluations qualité."""

    line_pk = models.BigAutoField(primary_key=True)
    id = models.PositiveBigIntegerField(default=generate_random_evaluation_int, db_index=True)

    # Clés étrangères vers les dimensions (schéma en flocons)
    date = models.ForeignKey(
        DateDim,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='evaluations',
    )
    user = models.ForeignKey(
        'User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='evaluations',
    )
    filiale = models.ForeignKey(
        Branch,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='evaluations',
    )
    laboratoire = models.ForeignKey(
        Laboratoire,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='evaluations',
    )

    # Mesures (champs métier)
    axe_evaluation = models.TextField(blank=True)
    criteres = models.TextField(blank=True)
    note = models.CharField(max_length=50, blank=True)
    ponderation = models.CharField(max_length=50, blank=True)
    observations = models.TextField(blank=True)

    # Indicateurs calculés (nouveaux dans le schéma en flocons)
    moy_ponderation = models.CharField(max_length=50, blank=True)
    tx_conformite = models.CharField(max_length=50, blank=True)

    # Champs dénormalisés conservés pour la compatibilité avec l'import Excel
    code = models.CharField(max_length=50, blank=True)
    filiale_name = models.CharField(max_length=150, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Evaluation #{self.line_pk}'


# ---------------------------------------------------------------------------
# Utilisateur authentifié par e-mail
# ---------------------------------------------------------------------------

class User(AbstractBaseUser, PermissionsMixin):
    """Application user authenticated with a unique email address."""

    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)

    class Role(models.TextChoices):
        GENERAL_MANAGER = 'general_manager', 'Responsable général'
        SECTOR_MANAGER = 'sector_manager', 'Responsable de secteur'
        USER = 'user', ' utilisateur'

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.USER)
    branch = models.ForeignKey(
        Branch,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='users',
    )
    sector = models.ForeignKey(
        Sector,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='users',
    )

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        ordering = ['email']

    def __str__(self):
        return self.email
