import json
import os
import re
import secrets
import threading
import time
import unicodedata
from datetime import datetime, timezone
from django.contrib.auth import authenticate, login, logout as auth_logout
from django.db import IntegrityError
from django.db.models import Max, Q
from django.db.models.deletion import ProtectedError
from django.db.models.functions import Lower
from django.http import JsonResponse, HttpResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from pathlib import Path
from .ml_inference import ModelInferenceError, predict_evaluations
from .mlops_status import get_backend_mlops_status
from .models import Branch, DateDim, Evaluation, Laboratoire, Sector, User

BASE_DIR = Path(__file__).resolve().parent.parent
_ENV_CACHE = {'path': None, 'mtime': None}
_CHATBOT_REPLY_CACHE = {}
_CHATBOT_REPLY_CACHE_TTL_SECONDS = 180
_EVALUATION_RESPONSE_CACHE = {}
_EVALUATION_RESPONSE_CACHE_TTL_SECONDS = 120


def load_env_file(path: Path, override: bool = False):
    if not path.exists():
        return

    current_mtime = path.stat().st_mtime
    if (
        override
        and _ENV_CACHE['path'] == str(path)
        and _ENV_CACHE['mtime'] == current_mtime
    ):
        return

    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and (override or key not in os.environ):
            os.environ[key] = value

    _ENV_CACHE['path'] = str(path)
    _ENV_CACHE['mtime'] = current_mtime

# ---------------------------------------------------------------------------
# Helpers — schéma en flocons
# ---------------------------------------------------------------------------

def get_or_create_laboratoire(name):
    """Cherche/crée un laboratoire à partir de son nom."""
    clean = (name or '').strip()
    if not clean:
        return None
    labo, _ = Laboratoire.objects.get_or_create(name__iexact=clean, defaults={'name': clean})
    return labo


def get_or_create_date(mois, annee):
    """Cherche/crée une date (Dim_date) à partir du mois et de l'année."""
    mois_clean = (mois or '').strip()
    annee_clean = (annee or '').strip()
    if not mois_clean and not annee_clean:
        return None
    trimestre = DateDim.compute_trimestre(mois_clean) if mois_clean else ''
    date, _ = DateDim.objects.get_or_create(
        mois__iexact=mois_clean,
        annee__iexact=annee_clean,
        defaults={'mois': mois_clean, 'annee': annee_clean, 'trimestre': trimestre},
    )
    return date


def compute_moy_ponderation(ponderation):
    """Convertit une pondération en pourcentage moyen."""
    value = (ponderation or '').strip().replace(',', '.')
    if not value:
        return ''
    try:
        return f'{float(value):.2f}'
    except ValueError:
        return value


def compute_tx_conformite(note):
    """Calcule le taux de conformité à partir de la note (/20)."""
    value = (note or '').strip().replace(',', '.')
    if not value:
        return ''
    try:
        note_num = float(value)
        tx = (note_num / 20.0) * 100
        return f'{tx:.1f}%'
    except ValueError:
        return value


def resolve_evaluation_id(raw_value=None, fallback=None):
    """Normalise un identifiant métier d'évaluation."""
    if raw_value:
        try:
            return int(str(raw_value).strip())
        except (ValueError, TypeError, AttributeError):
            pass
    if fallback:
        try:
            return int(str(fallback).strip())
        except (ValueError, TypeError, AttributeError):
            pass
    return 100000000 + secrets.randbelow(900000000)


def get_scoped_evaluations(user):
    """Retourne les évaluations visibles selon le rôle connecté."""
    qs = Evaluation.objects.select_related('filiale__sector__manager', 'laboratoire', 'date', 'user')

    if user.role == User.Role.GENERAL_MANAGER:
        return qs

    if user.role == User.Role.SECTOR_MANAGER and hasattr(user, 'managed_sector') and user.managed_sector:
        return qs.filter(
            Q(filiale__sector=user.managed_sector)
            | Q(user__sector=user.managed_sector)
        ).distinct()

    return qs.filter(user=user)


def apply_evaluation_filters(qs, request):
    """Applique les filtres communs sur les évaluations."""
    date_id = request.GET.get('date_id', '').strip()
    filiale_id = request.GET.get('filiale_id', '').strip()
    laboratoire_id = request.GET.get('laboratoire_id', '').strip()
    user_id = request.GET.get('user_id', '').strip()
    sector_id = request.GET.get('sector_id', '').strip()
    manager_id = request.GET.get('manager_id', '').strip()

    if date_id.isdigit():
        qs = qs.filter(date_id=int(date_id))
    if filiale_id.isdigit():
        qs = qs.filter(filiale_id=int(filiale_id))
    if laboratoire_id.isdigit():
        qs = qs.filter(laboratoire_id=int(laboratoire_id))
    if user_id.isdigit():
        qs = qs.filter(user_id=int(user_id))
    if sector_id.isdigit():
        qs = qs.filter(filiale__sector_id=int(sector_id))
    if manager_id.isdigit():
        qs = qs.filter(filiale__sector__manager_id=int(manager_id))

    return qs


def get_user_sector_name(user):
    """Retourne le secteur métier à afficher pour l'utilisateur."""
    if getattr(user, 'sector_id', None) and getattr(user, 'sector', None):
        return user.sector.name
    if user.role == User.Role.SECTOR_MANAGER and hasattr(user, 'managed_sector') and user.managed_sector:
        return user.managed_sector.name
    if user.branch and user.branch.sector:
        return user.branch.sector.name
    return ''


def resolve_user_sector_id(role, branch_id=None, managed_sector_id=None):
    """Résout le secteur direct à stocker sur l'utilisateur."""
    if role == User.Role.SECTOR_MANAGER:
        return managed_sector_id or None
    if role == User.Role.USER and branch_id:
        branch = Branch.objects.filter(pk=branch_id).values('sector_id').first()
        return branch['sector_id'] if branch else None
    return None


def sync_user_sector(user):
    """Synchronise le secteur direct d'un utilisateur à partir de son rôle."""
    sector_id = None
    if user.role == User.Role.SECTOR_MANAGER:
        managed_sector = getattr(user, 'managed_sector', None)
        sector_id = managed_sector.id if managed_sector else None
    elif user.role == User.Role.USER and user.branch_id:
        branch = Branch.objects.filter(pk=user.branch_id).values('sector_id').first()
        sector_id = branch['sector_id'] if branch else None

    if getattr(user, 'sector_id', None) != sector_id:
        user.sector_id = sector_id
        user.save(update_fields=['sector'])


def sync_branch_users_sector(branch):
    """Met à jour le secteur direct de tous les utilisateurs d'une filiale."""
    if branch is None:
        return
    User.objects.filter(branch=branch, role=User.Role.USER).exclude(sector_id=branch.sector_id).update(sector_id=branch.sector_id)


def _evaluation_cache_key(prefix, user, request=None):
    params = {}
    if request is not None:
        for name in [
            'date_id', 'filiale_id', 'laboratoire_id', 'user_id', 'sector_id',
            'manager_id', 'mois', 'annee', 'filiale_name', 'id', 'evaluation_id', 'since',
        ]:
            value = request.GET.get(name, '').strip()
            if value:
                params[name] = value

    return json.dumps(
        {
            'prefix': prefix,
            'user_id': getattr(user, 'id', None),
            'role': getattr(user, 'role', None),
            'params': params,
        },
        sort_keys=True,
        ensure_ascii=False,
    )


def _get_cached_evaluation_response(cache_key):
    entry = _EVALUATION_RESPONSE_CACHE.get(cache_key)
    if not entry:
        return None
    expires_at = entry.get('expires_at', 0)
    if expires_at <= time.time():
        _EVALUATION_RESPONSE_CACHE.pop(cache_key, None)
        return None
    return entry.get('payload')


def _set_cached_evaluation_response(cache_key, payload):
    _EVALUATION_RESPONSE_CACHE[cache_key] = {
        'payload': payload,
        'expires_at': time.time() + _EVALUATION_RESPONSE_CACHE_TTL_SECONDS,
    }


def invalidate_evaluation_response_cache():
    _EVALUATION_RESPONSE_CACHE.clear()


def build_evaluation_overview(evaluations, since_timestamp_ms=None):
    latest_created_at = evaluations.aggregate(latest_created_at=Max('created_at')).get('latest_created_at')
    payload = {
        'session_count': evaluations.values('id').distinct().count(),
        'row_count': evaluations.count(),
        'latest_created_at': latest_created_at.isoformat() if latest_created_at else None,
        'new_session_count': 0,
    }

    if since_timestamp_ms:
        try:
            since_dt = datetime.fromtimestamp(int(since_timestamp_ms) / 1000, tz=timezone.utc)
            payload['new_session_count'] = evaluations.filter(created_at__gt=since_dt).values('id').distinct().count()
        except (TypeError, ValueError, OSError, OverflowError):
            payload['new_session_count'] = 0

    return payload


def build_evaluation_summaries(evaluations):
    """Agrège les lignes détaillées en sessions d'évaluation."""
    sessions = {}
    rows = evaluations.order_by('-created_at').values(
        'line_pk',
        'id',
        'created_at',
        'date_id',
        'date__mois',
        'date__annee',
        'filiale_id',
        'filiale__code',
        'filiale__name',
        'filiale_name',
        'code',
        'filiale__sector_id',
        'filiale__sector__name',
        'filiale__sector__manager_id',
        'filiale__sector__manager__first_name',
        'filiale__sector__manager__last_name',
        'laboratoire_id',
        'laboratoire__name',
        'user_id',
        'user__first_name',
        'user__last_name',
        'note',
        'ponderation',
    )

    for row in rows.iterator(chunk_size=2000):
        key_parts = [
            row['date_id'] or 'no-date',
            row['filiale_id'] or row['filiale_name'] or 'no-filiale',
            row['laboratoire_id'] or 'no-lab',
            row['user_id'] or 'no-user',
        ]
        key = str(row['id']) if row['id'] else '|'.join(str(part) for part in key_parts)
        session = sessions.get(key)
        if session is None:
            manager_name = ' '.join(
                part for part in [
                    row['filiale__sector__manager__first_name'] or '',
                    row['filiale__sector__manager__last_name'] or '',
                ] if part
            ).strip()
            user_name = ' '.join(
                part for part in [
                    row['user__first_name'] or '',
                    row['user__last_name'] or '',
                ] if part
            ).strip()
            session = {
                'id': key,
                'line_pk': row['line_pk'],
                'mois': row['date__mois'] or '',
                'annee': row['date__annee'] or '',
                'filiale_name': row['filiale__name'] or row['filiale_name'] or '',
                'filiale_id': row['filiale_id'],
                'filiale_code': row['filiale__code'] or row['code'],
                'secteur_name': row['filiale__sector__name'] or '',
                'sector_id': row['filiale__sector_id'],
                'manager_id': row['filiale__sector__manager_id'],
                'manager_name': manager_name,
                'laboratoire_name': row['laboratoire__name'] or '',
                'laboratoire_id': row['laboratoire_id'],
                'user_name': user_name,
                'user_id': row['user_id'],
                'created_at': row['created_at'],
                'date_id': row['date_id'],
                'rows_count': 0,
                'total_weighted': 0.0,
                'total_weight': 0.0,
                'min_note': None,
                'max_note': None,
            }
            sessions[key] = session

        session['rows_count'] += 1

        try:
            note = float((row['note'] or '0').replace(',', '.'))
            weight = float((row['ponderation'] or '0').replace(',', '.'))
            session['total_weighted'] += note * weight
            session['total_weight'] += weight
            session['min_note'] = note if session['min_note'] is None else min(session['min_note'], note)
            session['max_note'] = note if session['max_note'] is None else max(session['max_note'], note)
        except (ValueError, TypeError, AttributeError):
            continue

    results = []
    for key, sess in sessions.items():
        note_moyenne = round(sess['total_weighted'] / sess['total_weight'], 2) if sess['total_weight'] > 0 else 0
        conformite = round((note_moyenne / 20.0) * 100, 1) if note_moyenne > 0 else 0
        periode = ' '.join(part for part in [sess['mois'], sess['annee']] if part).strip() or '—'

        results.append(
            {
                'id': sess['id'],
                'line_pk': sess['line_pk'],
                'key': key,
                'periode': periode,
                'mois': sess['mois'],
                'annee': sess['annee'],
                'date_id': sess['date_id'],
                'filiale_id': sess['filiale_id'],
                'filiale_code': sess['filiale_code'],
                'filiale_name': sess['filiale_name'] or '—',
                'secteur_name': sess['secteur_name'] or '—',
                'sector_id': sess['sector_id'],
                'manager_id': sess['manager_id'],
                'manager_name': sess['manager_name'] or '—',
                'laboratoire_id': sess['laboratoire_id'],
                'laboratoire_name': sess['laboratoire_name'] or '—',
                'user_id': sess['user_id'],
                'user_name': sess['user_name'] or '—',
                'note_moyenne': note_moyenne,
                'min_note': round(sess['min_note'], 2) if sess['min_note'] is not None else None,
                'max_note': round(sess['max_note'], 2) if sess['max_note'] is not None else None,
                'conformite_globale': conformite,
                'rows_count': sess['rows_count'],
                'created_at': sess['created_at'],
            }
        )

    results.sort(key=lambda item: (item['created_at'] is None, item['created_at'] or ''), reverse=True)
    return results


def normalize_search_text(value):
    text = str(value or '').strip().lower()
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(char for char in text if not unicodedata.combining(char))
    return re.sub(r'\s+', ' ', text)


def parse_float_text(value):
    text = str(value or '').strip().replace(',', '.')
    if not text:
        return None
    try:
        return float(text)
    except (ValueError, TypeError):
        return None


CHATBOT_MONTH_ALIASES = {
    'janvier': 'Janvier',
    'fevrier': 'Fevrier',
    'février': 'Fevrier',
    'mars': 'Mars',
    'avril': 'Avril',
    'mai': 'Mai',
    'juin': 'Juin',
    'juillet': 'Juillet',
    'aout': 'Aout',
    'août': 'Aout',
    'septembre': 'Septembre',
    'octobre': 'Octobre',
    'novembre': 'Novembre',
    'decembre': 'Decembre',
    'décembre': 'Decembre',
}

CHATBOT_STOPWORDS = {
    'a', 'au', 'aux', 'avec', 'base', 'bases', 'bonjour', 'bonsoir', 'chatbot', 'combien',
    'comment', 'conformite', 'conformites', 'critere', 'criteres', 'dans', 'data', 'database',
    'de', 'des', 'du', 'donne', 'donnees', 'donnee', 'est', 'et', 'evaluation', 'evaluations',
    'filiale', 'filiales', 'il', 'je', 'la', 'le', 'les', 'ligne', 'lignes', 'me', 'mes',
    'mois', 'mon', 'montre', 'moyenne', 'non', 'note', 'notes', 'observation', 'observations',
    'ou', 'par', 'pas', 'plus', 'pour', 'pourquoi', 'quand', 'que', 'quel', 'quelle', 'quelles',
    'quels', 'question', 'recherche', 'rechercher', 'secteur', 'secteurs', 'sql', 'sqlserver',
    'sur', 'taux', 'top', 'une', 'utilisateur', 'utilisateurs', 'veut', 'voir', 'ia',
}


def format_period_label(month, year):
    parts = [str(part).strip() for part in [month, year] if str(part or '').strip()]
    return ' '.join(parts) if parts else 'tout le perimetre'


def format_scope_label(filters):
    parts = []
    if filters.get('branch_name'):
        parts.append(f"filiale {filters['branch_name']}")
    if filters.get('sector_name'):
        parts.append(f"secteur {filters['sector_name']}")
    if filters.get('user_name'):
        parts.append(f"utilisateur {filters['user_name']}")
    period_label = format_period_label(filters.get('month_label'), filters.get('year'))
    if period_label != 'tout le perimetre':
        parts.append(period_label)
    return ', '.join(parts) if parts else 'tout le perimetre visible'


def compute_chatbot_metrics(rows):
    metrics = {
        'line_count': 0,
        'audit_ids': set(),
        'weighted_total': 0.0,
        'weight_total': 0.0,
        'non_conformities': 0,
        'branches': {},
        'users': {},
        'sectors': {},
    }

    for row in rows:
        note = parse_float_text(row.get('note'))
        weight = parse_float_text(row.get('ponderation')) or 0.0
        metrics['line_count'] += 1
        if row.get('id') is not None:
            metrics['audit_ids'].add(row['id'])
        if note is not None and note < 16:
            metrics['non_conformities'] += 1
        if note is not None:
            metrics['weighted_total'] += note * weight
            metrics['weight_total'] += weight

        branch_name = row.get('filiale__name') or row.get('filiale_name') or '—'
        sector_name = row.get('filiale__sector__name') or '—'
        user_name = ' '.join(
            part for part in [row.get('user__first_name') or '', row.get('user__last_name') or ''] if part
        ).strip() or row.get('user__email') or '—'

        for bucket, key in [
            (metrics['branches'], branch_name),
            (metrics['users'], user_name),
            (metrics['sectors'], sector_name),
        ]:
            if key not in bucket:
                bucket[key] = {'weighted_total': 0.0, 'weight_total': 0.0, 'lines': 0, 'audit_ids': set()}
            bucket[key]['lines'] += 1
            if row.get('id') is not None:
                bucket[key]['audit_ids'].add(row['id'])
            if note is not None:
                bucket[key]['weighted_total'] += note * weight
                bucket[key]['weight_total'] += weight

    metrics['audit_count'] = len(metrics['audit_ids'])
    metrics['average_note'] = round(metrics['weighted_total'] / metrics['weight_total'], 2) if metrics['weight_total'] else 0.0
    metrics['conformity_pct'] = round((metrics['average_note'] / 20.0) * 100, 2) if metrics['weight_total'] else 0.0
    return metrics


def rank_chatbot_bucket(bucket, reverse=True):
    ranked = []
    for name, stats in bucket.items():
        if not stats['weight_total']:
            continue
        average_note = stats['weighted_total'] / stats['weight_total']
        ranked.append(
            {
                'name': name,
                'average_note': round(average_note, 2),
                'conformity_pct': round((average_note / 20.0) * 100, 2),
                'lines': stats['lines'],
                'audit_count': len(stats['audit_ids']),
            }
        )
    return sorted(ranked, key=lambda item: (item['average_note'], item['audit_count']), reverse=reverse)


def extract_chatbot_filters(question, evaluations):
    normalized = normalize_search_text(question)
    filters = {}

    year_match = re.search(r'\b(20\d{2})\b', normalized)
    if year_match:
        filters['year'] = year_match.group(1)

    for month_alias, canonical in CHATBOT_MONTH_ALIASES.items():
        if re.search(rf'\b{re.escape(normalize_search_text(month_alias))}\b', normalized):
            filters['month_label'] = canonical
            break

    branch_rows = list(
        evaluations.exclude(filiale_id=None).values('filiale_id', 'filiale__name', 'filiale__code').distinct()
    )
    for item in branch_rows:
        branch_name = str(item.get('filiale__name') or '').strip()
        branch_code = str(item.get('filiale__code') or '').strip()
        if branch_name and normalize_search_text(branch_name) in normalized:
            filters['branch_id'] = item['filiale_id']
            filters['branch_name'] = branch_name
            break
        if branch_code and re.search(rf'\b{re.escape(branch_code)}\b', normalized):
            filters['branch_id'] = item['filiale_id']
            filters['branch_name'] = branch_name or branch_code
            break

    sector_rows = list(
        evaluations.exclude(filiale__sector_id=None).values('filiale__sector_id', 'filiale__sector__name').distinct()
    )
    for item in sector_rows:
        sector_name = str(item.get('filiale__sector__name') or '').strip()
        if sector_name and normalize_search_text(sector_name) in normalized:
            filters['sector_id'] = item['filiale__sector_id']
            filters['sector_name'] = sector_name
            break

    user_rows = list(
        evaluations.exclude(user_id=None).values('user_id', 'user__first_name', 'user__last_name', 'user__email').distinct()
    )
    for item in user_rows:
        full_name = ' '.join(
            part for part in [item.get('user__first_name') or '', item.get('user__last_name') or ''] if part
        ).strip()
        email = str(item.get('user__email') or '').strip()
        if full_name and normalize_search_text(full_name) in normalized:
            filters['user_id'] = item['user_id']
            filters['user_name'] = full_name
            break
        if email and normalize_search_text(email) in normalized:
            filters['user_id'] = item['user_id']
            filters['user_name'] = full_name or email
            break

    return filters


def search_evaluation_rows(rows, question, limit=5):
    normalized_question = normalize_search_text(question)
    raw_tokens = re.findall(r'[a-zA-Z0-9_]+', normalized_question)
    tokens = [token for token in raw_tokens if len(token) >= 3 and token not in CHATBOT_STOPWORDS and not token.isdigit()]
    if not tokens:
        return []

    scored = []
    for row in rows:
        haystack = normalize_search_text(
            ' '.join(
                [
                    row.get('axe_evaluation') or '',
                    row.get('criteres') or '',
                    row.get('observations') or '',
                    row.get('filiale__name') or row.get('filiale_name') or '',
                ]
            )
        )
        hits = sum(1 for token in tokens if token in haystack)
        if hits > 0:
            scored.append((hits, row))

    scored.sort(
        key=lambda item: (
            item[0],
            parse_float_text(item[1].get('note')) if parse_float_text(item[1].get('note')) is not None else -1,
        ),
        reverse=True,
    )
    return [row for _, row in scored[:limit]]


def build_database_chatbot_reply(user, question):
    if not getattr(user, 'is_authenticated', False) or not hasattr(user, 'role'):
        return None

    normalized = normalize_search_text(question)
    db_keywords = [
        'base', 'donnee', 'donnees', 'evaluation', 'evaluations', 'audit', 'audits', 'filiale',
        'secteur', 'note', 'conformite', 'non conform', 'utilisateur', 'laboratoire',
        'critere', 'criteres', 'observation', 'top', 'meilleur', 'pire', 'combien',
        'moyenne', 'taux', 'sql',
    ]
    if not any(keyword in normalized for keyword in db_keywords):
        return None

    scoped_evaluations = get_scoped_evaluations(user)
    filters = extract_chatbot_filters(question, scoped_evaluations)
    filtered_qs = scoped_evaluations
    if filters.get('branch_id'):
        filtered_qs = filtered_qs.filter(filiale_id=filters['branch_id'])
    if filters.get('sector_id'):
        filtered_qs = filtered_qs.filter(filiale__sector_id=filters['sector_id'])
    if filters.get('user_id'):
        filtered_qs = filtered_qs.filter(user_id=filters['user_id'])
    if filters.get('year'):
        filtered_qs = filtered_qs.filter(date__annee=filters['year'])
    if filters.get('month_label'):
        month_options = [filters['month_label']]
        if filters['month_label'] == 'Aout':
            month_options.append('Août')
        if filters['month_label'] == 'Fevrier':
            month_options.append('Février')
        if filters['month_label'] == 'Decembre':
            month_options.append('Décembre')
        filtered_qs = filtered_qs.filter(date__mois__in=month_options)

    rows = list(
        filtered_qs.values(
            'line_pk', 'id', 'axe_evaluation', 'criteres', 'observations', 'note', 'ponderation',
            'filiale_name', 'filiale__name', 'filiale__sector__name', 'filiale__code', 'laboratoire__name',
            'date__mois', 'date__annee', 'user__first_name', 'user__last_name', 'user__email',
        )
    )
    if not rows:
        return f"Je n'ai trouve aucune donnee pour {format_scope_label(filters)}."

    metrics = compute_chatbot_metrics(rows)
    scope_label = format_scope_label(filters)
    summaries = build_evaluation_summaries(filtered_qs)
    has_count = any(term in normalized for term in ['combien', 'nombre', 'total'])
    asks_top = any(term in normalized for term in ['top', 'meilleur', 'meilleure', 'plus performant', 'plus performante', 'plus conforme'])
    asks_bottom = any(term in normalized for term in ['pire', 'moins performant', 'moins performante', 'moins conforme', 'plus faible'])
    asks_list = any(term in normalized for term in ['liste', 'quelles', 'quels', 'montre', 'affiche'])
    asks_branch = 'filiale' in normalized
    asks_sector = 'secteur' in normalized
    asks_user = any(term in normalized for term in ['utilisateur', 'auditeur', 'responsable'])
    asks_non_conformity = 'non conform' in normalized
    asks_conformity = 'conformite' in normalized or 'conforme' in normalized
    asks_note = 'note' in normalized or 'moyenne' in normalized
    asks_criteria = any(term in normalized for term in ['critere', 'criteres', 'axe', 'observation', 'observations'])

    if has_count and any(term in normalized for term in ['audit', 'evaluation', 'evaluations', 'session', 'sessions']):
        return (
            f"Pour {scope_label}, j'ai trouve {metrics['audit_count']} audits et {metrics['line_count']} lignes d'evaluation. "
            f"La note moyenne ponderee est de {metrics['average_note']:.2f}/20, soit {metrics['conformity_pct']:.2f}% de conformite."
        )

    if has_count and asks_branch:
        branch_count = len([name for name in metrics['branches'].keys() if name and name != '—'])
        return f"Pour {scope_label}, j'ai trouve {branch_count} filiales avec des evaluations."

    if has_count and asks_sector:
        sector_count = len([name for name in metrics['sectors'].keys() if name and name != '—'])
        return f"Pour {scope_label}, j'ai trouve {sector_count} secteurs avec des evaluations."

    if has_count and asks_user:
        user_count = len([name for name in metrics['users'].keys() if name and name != '—'])
        return f"Pour {scope_label}, j'ai trouve {user_count} utilisateurs rattaches aux evaluations visibles."

    if asks_non_conformity:
        share = (metrics['non_conformities'] / metrics['line_count'] * 100.0) if metrics['line_count'] else 0.0
        return (
            f"Pour {scope_label}, j'ai compte {metrics['non_conformities']} non-conformites sur {metrics['line_count']} lignes, "
            f"soit {share:.2f}% des criteres. La note moyenne ponderee est de {metrics['average_note']:.2f}/20."
        )

    if asks_conformity and not asks_top and not asks_bottom:
        return (
            f"Le taux de conformite pour {scope_label} est de {metrics['conformity_pct']:.2f}%. "
            f"Cela correspond a une note moyenne ponderee de {metrics['average_note']:.2f}/20 sur {metrics['audit_count']} audits."
        )

    if asks_note and not asks_top and not asks_bottom:
        return (
            f"Pour {scope_label}, la note moyenne ponderee est de {metrics['average_note']:.2f}/20. "
            f"J'ai utilise {metrics['audit_count']} audits et {metrics['line_count']} lignes d'evaluation."
        )

    if asks_top and asks_branch:
        ranking = rank_chatbot_bucket(metrics['branches'], reverse=True)[:3]
        if not ranking:
            return f"Je n'ai pas assez de donnees filiale pour {scope_label}."
        lines = [f"{index + 1}. {item['name']} - {item['average_note']:.2f}/20 ({item['conformity_pct']:.2f}% conformite)" for index, item in enumerate(ranking)]
        return f"Top filiales pour {scope_label}:\n" + '\n'.join(lines)

    if asks_bottom and asks_branch:
        ranking = rank_chatbot_bucket(metrics['branches'], reverse=False)[:3]
        if not ranking:
            return f"Je n'ai pas assez de donnees filiale pour {scope_label}."
        lines = [f"{index + 1}. {item['name']} - {item['average_note']:.2f}/20 ({item['conformity_pct']:.2f}% conformite)" for index, item in enumerate(ranking)]
        return f"Filiales les moins performantes pour {scope_label}:\n" + '\n'.join(lines)

    if asks_top and asks_user:
        ranking = rank_chatbot_bucket(metrics['users'], reverse=True)[:3]
        if not ranking:
            return f"Je n'ai pas assez de donnees utilisateur pour {scope_label}."
        lines = [f"{index + 1}. {item['name']} - {item['average_note']:.2f}/20 sur {item['audit_count']} audits" for index, item in enumerate(ranking)]
        return f"Top utilisateurs pour {scope_label}:\n" + '\n'.join(lines)

    if asks_list and asks_branch:
        ranking = rank_chatbot_bucket(metrics['branches'], reverse=True)
        branch_names = [item['name'] for item in ranking[:8]]
        if not branch_names:
            return f"Je n'ai pas trouve de filiales pour {scope_label}."
        return f"Filiales trouvees pour {scope_label}: " + ', '.join(branch_names) + '.'

    if asks_list and asks_sector:
        ranking = rank_chatbot_bucket(metrics['sectors'], reverse=True)
        sector_names = [item['name'] for item in ranking[:8]]
        if not sector_names:
            return f"Je n'ai pas trouve de secteurs pour {scope_label}."
        return f"Secteurs trouves pour {scope_label}: " + ', '.join(sector_names) + '.'

    if asks_criteria:
        matches = search_evaluation_rows(rows, question)
        if matches:
            lines = []
            for row in matches[:5]:
                note = parse_float_text(row.get('note')) or 0.0
                period = format_period_label(row.get('date__mois'), row.get('date__annee'))
                branch_name = row.get('filiale__name') or row.get('filiale_name') or '—'
                criterion = (row.get('criteres') or row.get('axe_evaluation') or '').strip()
                criterion = criterion[:140] + '...' if len(criterion) > 140 else criterion
                lines.append(f"- {branch_name}, {period}, note {note:.2f}/20: {criterion}")
            return "J'ai trouve ces lignes proches de votre question:\n" + '\n'.join(lines)

    latest_sessions = summaries[:3]
    latest_labels = [f"{item['filiale_name']} ({item['periode']}) - {item['note_moyenne']:.2f}/20" for item in latest_sessions]
    latest_text = ' ; '.join(latest_labels) if latest_labels else 'aucun audit recent'
    return (
        f"Pour {scope_label}, j'ai trouve {metrics['audit_count']} audits et {metrics['line_count']} lignes. "
        f"Note moyenne ponderee: {metrics['average_note']:.2f}/20, conformite: {metrics['conformity_pct']:.2f}%, "
        f"non-conformites: {metrics['non_conformities']}. Derniers audits: {latest_text}."
    )


def build_evaluation_session_rows(evaluations):
    """Construit le détail des lignes d'une session d'évaluation."""
    rows = list(evaluations.order_by('line_pk'))
    axes = {}

    for ev in rows:
        axe = (ev.axe_evaluation or 'Sans axe').strip()
        axes.setdefault(axe, []).append(ev)

    axe_stats = {}
    for axe, evs in axes.items():
        total_weighted = 0.0
        total_weight = 0.0
        for ev in evs:
            try:
                note = float(ev.note or 0)
                weight = float(ev.ponderation or 0)
                total_weighted += note * weight
                total_weight += weight
            except (ValueError, TypeError):
                continue

        moyenne = total_weighted / total_weight if total_weight > 0 else 0.0
        axe_stats[axe] = {
            'moyenne': round(moyenne, 2),
            'conformite': round((moyenne / 20.0) * 100, 2) if moyenne > 0 else 0.0,
        }

    return [
        {
            'id': int(ev.id) if ev.id else ev.line_pk,
            'line_pk': ev.line_pk,
            'filiale_id': ev.filiale_id,
            'filiale_name': ev.filiale.name if ev.filiale else ev.filiale_name or '',
            'filiale_code': ev.filiale.code if ev.filiale else (ev.code or ''),
            'code': ev.code or (ev.filiale.code if ev.filiale else ''),
            'secteur_name': ev.filiale.sector.name if ev.filiale and ev.filiale.sector else '',
            'manager_name': (
                f'{ev.filiale.sector.manager.first_name} {ev.filiale.sector.manager.last_name}'.strip()
                if ev.filiale and ev.filiale.sector and ev.filiale.sector.manager
                else ''
            ),
            'laboratoire_id': ev.laboratoire_id,
            'laboratoire_name': ev.laboratoire.name if ev.laboratoire else '',
            'date_id': ev.date_id,
            'mois': ev.date.mois if ev.date else '',
            'annee': ev.date.annee if ev.date else '',
            'trimestre': ev.date.trimestre if ev.date else '',
            'user_id': ev.user_id,
            'user_name': f'{ev.user.first_name} {ev.user.last_name}'.strip() if ev.user else '',
            'axe_evaluation': ev.axe_evaluation,
            'criteres': ev.criteres,
            'note': ev.note,
            'ponderation': ev.ponderation,
            'observations': ev.observations,
            'moy_ponderation': ev.moy_ponderation,
            'tx_conformite': ev.tx_conformite,
            'created_at': ev.created_at,
            'updated_at': ev.updated_at,
            'moyenne_axe': axe_stats[(ev.axe_evaluation or 'Sans axe').strip()]['moyenne'],
            'conformite_axe': axe_stats[(ev.axe_evaluation or 'Sans axe').strip()]['conformite'],
        }
        for ev in rows
    ]


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@csrf_exempt
def register(request):
    data = json.loads(request.body or '{}')
    email = data.get('email', '').strip()
    password = data.get('password', '')
    first_name = data.get('first_name', '').strip()
    last_name = data.get('last_name', '').strip()
    valid_password = (
        len(password) >= 8
        and re.search(r'[A-Z]', password)
        and re.search(r'\d', password)
        and re.search(r'[^A-Za-z0-9]', password)
    )
    if request.method != 'POST' or '@' not in email or not valid_password:
        return JsonResponse(
            {'detail': 'E-mail valide et mot de passe avec 8 caractères, majuscule, chiffre et caractère spécial requis.'},
            status=400,
        )
    if User.objects.filter(email=email).exists():
        return JsonResponse({'detail': 'Cet e-mail existe déjà.'}, status=400)
    role = data.get('role', User.Role.USER)
    if role not in User.Role.values:
        role = User.Role.USER
    if role == User.Role.GENERAL_MANAGER:
        user = User.objects.create_user(
            email,
            password,
            role=role,
            first_name=first_name,
            last_name=last_name,
            is_staff=True,
        )
    else:
        user = User.objects.create_user(
            email,
            password,
            role=role,
            first_name=first_name,
            last_name=last_name,
        )
    login(request, user)
    return JsonResponse(
        {
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'role': user.role,
        },
        status=201,
    )


def scope(request):
    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Authentification requise.'}, status=401)
    user = request.user
    lite = request.GET.get('lite') in {'1', 'true', 'yes'}

    if lite:
        response = JsonResponse(
            {
                'role': user.role,
                'sectors': [],
                'branches': [],
                'users': [],
                'sectorManagers': [],
                'me': {
                    'id': user.id,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'email': user.email,
                    'branch_id': user.branch_id,
                    'sector_id': user.sector_id,
                    'sector__name': get_user_sector_name(user) or None,
                    'branch_code': user.branch.code if user.branch else None,
                    'branch__name': user.branch.name if user.branch else None,
                    'branch__sector__name': user.branch.sector.name if user.branch and user.branch.sector else None,
                    'managed_sector_id': user.managed_sector.id if hasattr(user, 'managed_sector') and user.managed_sector else None,
                    'managed_sector__name': user.managed_sector.name if hasattr(user, 'managed_sector') and user.managed_sector else None,
                    'avatar': user.avatar.url if user.avatar else None,
                },
            }
        )
        return response

    if user.role == User.Role.GENERAL_MANAGER:
        sectors = Sector.objects.all()
        branches = Branch.objects.select_related('sector').all()
        users = User.objects.filter(role=User.Role.USER).select_related('branch', 'sector').all()
        sector_managers = (
            User.objects.filter(role=User.Role.SECTOR_MANAGER)
            .select_related('managed_sector', 'sector')
            .all()
        )
    elif user.role == User.Role.SECTOR_MANAGER and hasattr(user, 'managed_sector'):
        sectors = Sector.objects.filter(pk=user.managed_sector.pk)
        branches = user.managed_sector.branches.all()
        users = (
            User.objects.filter(sector=user.managed_sector, role=User.Role.USER)
            .select_related('branch', 'sector')
        )
        sector_managers = User.objects.filter(pk=user.pk).select_related('managed_sector', 'sector')
    else:
        sectors = Sector.objects.none()
        branches = Branch.objects.filter(pk=user.branch_id) if user.branch_id else Branch.objects.none()
        users = User.objects.filter(pk=user.pk).select_related('branch', 'sector')
        sector_managers = User.objects.none()
    sectors_payload = list(sectors.values('id', 'name', 'manager_id', 'manager__first_name', 'manager__last_name'))
    branches_payload = list(branches.values('id', 'code', 'name', 'sector_id', 'sector__name'))
    users_payload = list(
        users.values(
            'id',
            'email',
            'first_name',
            'last_name',
            'role',
            'branch_id',
            'branch__name',
            'branch__sector__name',
            'sector_id',
            'sector__name',
            'is_active',
            'date_joined',
        )
    )
    sector_managers_payload = list(
        sector_managers.values(
            'id',
            'email',
            'first_name',
            'last_name',
            'role',
            'branch_id',
            'branch__name',
            'sector_id',
            'sector__name',
            'managed_sector__id',
            'managed_sector__name',
            'is_active',
            'date_joined',
        )
    )
    response = JsonResponse(
        {
            'role': user.role,
            'sectors': sectors_payload,
            'branches': branches_payload,
            'users': users_payload,
            'sectorManagers': sector_managers_payload,
            'me': {
                'id': user.id,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'email': user.email,
                'branch_id': user.branch_id,
                'sector_id': user.sector_id,
                'sector__name': get_user_sector_name(user) or None,
                'branch_code': user.branch.code if user.branch else None,
                'branch__name': user.branch.name if user.branch else None,
                'branch__sector__name': user.branch.sector.name if user.branch and user.branch.sector else None,
                'managed_sector_id': user.managed_sector.id if hasattr(user, 'managed_sector') and user.managed_sector else None,
                'managed_sector__name': user.managed_sector.name if hasattr(user, 'managed_sector') and user.managed_sector else None,
                'avatar': user.avatar.url if user.avatar else None,
            },
        }
    )
    return response


@csrf_exempt
def login_view(request):
    data = json.loads(request.body or '{}')
    user = authenticate(
        request,
        email=data.get('email', ''),
        password=data.get('password', ''),
    )
    if request.method != 'POST' or user is None:
        return JsonResponse({'detail': 'E-mail ou mot de passe incorrect.'}, status=401)
    login(request, user)
    return JsonResponse(
        {
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'role': user.role,
        }
    )


@csrf_exempt
def admin_login(request):
    data = json.loads(request.body or '{}')
    user = authenticate(
        request,
        email=data.get('email', ''),
        password=data.get('password', ''),
    )
    if request.method != 'POST' or user is None or not user.is_staff:
        return JsonResponse({'detail': 'Accès administrateur refusé.'}, status=403)
    login(request, user)
    return JsonResponse({'email': user.email, 'isStaff': True})


@csrf_exempt
def logout_view(request):
    if request.method != 'POST':
        return JsonResponse({'detail': 'Méthode non autorisée.'}, status=405)

    auth_logout(request)
    return JsonResponse({'success': True})


@csrf_exempt
def chatbot_reply(request):
    if request.method != 'POST':
        return JsonResponse({'detail': 'Méthode non autorisée.'}, status=405)

    load_env_file(BASE_DIR / '.env', override=True)
    data = json.loads(request.body or '{}')
    user_message = str(data.get('message', '')).strip()
    wants_stream = bool(data.get('stream'))
    if not user_message:
        return JsonResponse({'detail': 'Le message est requis.'}, status=400)

    if len(user_message) > 1500:
        return JsonResponse({'detail': 'Le message est trop long. Limitez-vous à 1500 caractères.'}, status=400)

    history = data.get('history') or []
    role = str(data.get('role', '')).strip()
    sector = str(data.get('sector', '')).strip()
    database_reply = build_database_chatbot_reply(request.user, user_message)
    display_role = {
        User.Role.GENERAL_MANAGER: 'administrateur',
        User.Role.SECTOR_MANAGER: 'responsable de secteur',
        User.Role.USER: 'utilisateur',
    }.get(role, 'visiteur')

    system_prompt = (
        "Tu es l'assistant qualite de l'application interne de gestion des evaluations qualite. "
        "Reponds en francais, de facon concrete et breve, en 2 a 4 phrases courtes et utiles. "
        "Reste centre sur: evaluations, conformite, axes, criteres, ponderations, observations, secteurs, filiales, laboratoires, roles, tableaux de bord et usage des ecrans. "
        "Si la question est hors sujet, recentre poliment sur l'application et le domaine qualite."
    )

    context_hint = f"Contexte utilisateur: rôle={display_role}"
    if sector:
        context_hint += f", secteur={sector}"

    messages = [
        {'role': 'system', 'content': system_prompt},
        {'role': 'system', 'content': context_hint},
    ]

    history_window = history[-1:]
    for item in history_window:
        item_role = str(item.get('role', '')).strip()
        item_text = str(item.get('text', '')).strip()
        if item_role in {'user', 'assistant'} and item_text:
            messages.append({'role': item_role, 'content': item_text[:240]})

    messages.append({'role': 'user', 'content': user_message})

    provider = os.environ.get('AI_PROVIDER', '').strip().lower()
    if not provider:
        if os.environ.get('MISTRAL_API_KEY', '').strip():
            provider = 'mistral'
        elif os.environ.get('OLLAMA_API_KEY', '').strip():
            provider = 'ollama'
        else:
            provider = 'gemini' if os.environ.get('GOOGLE_API_KEY', '').strip() else 'openai'

    cache_history_fingerprint = [
        {
            'role': str(item.get('role', '')).strip(),
            'text': str(item.get('text', '')).strip()[:120],
        }
        for item in history_window
        if str(item.get('role', '')).strip() in {'user', 'assistant'} and str(item.get('text', '')).strip()
    ]
    cache_key = json.dumps(
        {
            'provider': provider,
            'user_id': getattr(request.user, 'id', None),
            'branch_id': getattr(request.user, 'branch_id', None),
            'managed_sector_id': getattr(getattr(request.user, 'managed_sector', None), 'id', None),
            'role': role,
            'sector': sector,
            'message': user_message.lower(),
            'history': cache_history_fingerprint,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    cached_entry = _CHATBOT_REPLY_CACHE.get(cache_key)
    if cached_entry and (time.time() - cached_entry['ts']) <= _CHATBOT_REPLY_CACHE_TTL_SECONDS:
        if wants_stream:
            stream_response = StreamingHttpResponse(
                iter([
                    f"data: {json.dumps({'delta': cached_entry['reply']}, ensure_ascii=False)}\n\n",
                    f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n",
                ]),
                content_type='text/event-stream',
            )
            stream_response['Cache-Control'] = 'no-cache'
            stream_response['X-Accel-Buffering'] = 'no'
            return stream_response
        return JsonResponse({'reply': cached_entry['reply']})

    if database_reply:
        _CHATBOT_REPLY_CACHE[cache_key] = {'reply': database_reply, 'ts': time.time()}
        if wants_stream:
            stream_response = StreamingHttpResponse(
                iter([
                    f"data: {json.dumps({'delta': database_reply}, ensure_ascii=False)}\n\n",
                    f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n",
                ]),
                content_type='text/event-stream',
            )
            stream_response['Cache-Control'] = 'no-cache'
            stream_response['X-Accel-Buffering'] = 'no'
            return stream_response
        return JsonResponse({'reply': database_reply})

    try:
        import urllib.error
        import urllib.request

        if provider == 'gemini':
            api_key = os.environ.get('GOOGLE_API_KEY', '').strip()
            if not api_key:
                return JsonResponse(
                    {'detail': 'Le chatbot IA n’est pas encore configuré. Ajoutez GOOGLE_API_KEY pour activer Gemini.'},
                    status=503,
                )

            gemini_payload = {
                'system_instruction': {
                    'parts': [{'text': f'{system_prompt}\n{context_hint}'}]
                },
                'contents': [
                    {
                        'role': 'model' if item['role'] == 'assistant' else 'user',
                        'parts': [{'text': item['content']}],
                    }
                    for item in messages
                    if item['role'] in {'user', 'assistant'}
                ],
                'generationConfig': {
                    'temperature': 0.35,
                    'maxOutputTokens': 140,
                },
            }
            requested_model = os.environ.get('GEMINI_CHAT_MODEL', 'gemini-flash-latest').strip() or 'gemini-flash-latest'
            gemini_models = []
            for model_name in [requested_model, 'gemini-flash-latest', 'gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-2.0-flash-lite']:
                if model_name not in gemini_models:
                    gemini_models.append(model_name)

            last_error_detail = 'Le service Gemini est momentanément indisponible.'
            reply = ''
            for model in gemini_models:
                try:
                    response = urllib.request.urlopen(
                        urllib.request.Request(
                            f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
                            data=json.dumps(gemini_payload).encode('utf-8'),
                            headers={
                                'Content-Type': 'application/json',
                                'X-goog-api-key': api_key,
                            },
                            method='POST',
                        ),
                        timeout=30,
                    )
                    response_data = json.loads(response.read().decode('utf-8'))
                    reply = ''.join(
                        part.get('text', '')
                        for part in response_data.get('candidates', [{}])[0]
                        .get('content', {})
                        .get('parts', [])
                    ).strip()
                    if reply:
                        break
                except urllib.error.HTTPError as exc:
                    try:
                        error_payload = json.loads(exc.read().decode('utf-8'))
                        detail = error_payload.get('error', {}).get('message') or 'Erreur du service Gemini.'
                    except Exception:
                        detail = 'Erreur du service Gemini.'
                    last_error_detail = detail
                    detail_lower = detail.lower()
                    if (
                        'not found' in detail_lower
                        or 'not supported' in detail_lower
                        or 'quota exceeded' in detail_lower
                        or 'rate limit' in detail_lower
                    ):
                        continue
                    break

            if not reply:
                return JsonResponse({'detail': last_error_detail}, status=502)
        elif provider == 'mistral':
            api_key = os.environ.get('MISTRAL_API_KEY', '').strip()
            if not api_key:
                return JsonResponse(
                    {'detail': 'Le chatbot IA n’est pas encore configuré. Ajoutez MISTRAL_API_KEY pour activer Mistral.'},
                    status=503,
                )

            mistral_payload = {
                'model': os.environ.get('MISTRAL_CHAT_MODEL', 'mistral-small-latest').strip() or 'mistral-small-latest',
                'messages': messages,
                'temperature': 0.35,
                'max_tokens': 140,
                'stream': wants_stream,
            }
            if wants_stream:
                def mistral_stream():
                    reply_chunks = []
                    try:
                        response = urllib.request.urlopen(
                            urllib.request.Request(
                                'https://api.mistral.ai/v1/chat/completions',
                                data=json.dumps(mistral_payload).encode('utf-8'),
                                headers={
                                    'Content-Type': 'application/json',
                                    'Authorization': f'Bearer {api_key}',
                                },
                                method='POST',
                            ),
                            timeout=20,
                        )
                        for raw_line in response:
                            line = raw_line.decode('utf-8', errors='ignore').strip()
                            if not line.startswith('data:'):
                                continue
                            payload_text = line[5:].strip()
                            if not payload_text:
                                continue
                            if payload_text == '[DONE]':
                                break
                            try:
                                chunk_payload = json.loads(payload_text)
                            except json.JSONDecodeError:
                                continue
                            choice = (chunk_payload.get('choices') or [{}])[0]
                            delta = choice.get('delta', {}) if isinstance(choice, dict) else {}
                            chunk_content = delta.get('content', '')
                            if isinstance(chunk_content, list):
                                chunk_text = ''.join(
                                    part.get('text', '')
                                    for part in chunk_content
                                    if isinstance(part, dict)
                                )
                            else:
                                chunk_text = str(chunk_content or '')
                            if not chunk_text:
                                continue
                            reply_chunks.append(chunk_text)
                            yield f"data: {json.dumps({'delta': chunk_text}, ensure_ascii=False)}\n\n"

                        reply = ''.join(reply_chunks).strip()
                        if reply:
                            _CHATBOT_REPLY_CACHE[cache_key] = {'reply': reply, 'ts': time.time()}
                            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
                            return

                        yield f"data: {json.dumps({'error': 'Aucune réponse n’a été générée.'}, ensure_ascii=False)}\n\n"
                    except urllib.error.HTTPError as exc:
                        try:
                            error_payload = json.loads(exc.read().decode('utf-8'))
                            detail = error_payload.get('error', {}).get('message') or 'Erreur du service IA.'
                        except Exception:
                            detail = 'Erreur du service IA.'
                        yield f"data: {json.dumps({'error': detail}, ensure_ascii=False)}\n\n"
                    except Exception:
                        partial_reply = ''.join(reply_chunks).strip()
                        if partial_reply:
                            _CHATBOT_REPLY_CACHE[cache_key] = {'reply': partial_reply, 'ts': time.time()}
                            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
                            return
                        yield f"data: {json.dumps({'error': 'Le chatbot IA est momentanément indisponible.'}, ensure_ascii=False)}\n\n"

                stream_response = StreamingHttpResponse(mistral_stream(), content_type='text/event-stream')
                stream_response['Cache-Control'] = 'no-cache'
                stream_response['X-Accel-Buffering'] = 'no'
                return stream_response
            response = urllib.request.urlopen(
                urllib.request.Request(
                    'https://api.mistral.ai/v1/chat/completions',
                    data=json.dumps(mistral_payload).encode('utf-8'),
                    headers={
                        'Content-Type': 'application/json',
                        'Authorization': f'Bearer {api_key}',
                    },
                    method='POST',
                ),
                timeout=20,
            )
            response_data = json.loads(response.read().decode('utf-8'))
            message_content = (
                response_data.get('choices', [{}])[0]
                .get('message', {})
                .get('content', '')
            )
            if isinstance(message_content, list):
                reply = ''.join(
                    chunk.get('text', '')
                    for chunk in message_content
                    if isinstance(chunk, dict)
                ).strip()
            else:
                reply = str(message_content or '').strip()
        elif provider == 'ollama':
            ollama_host = os.environ.get('OLLAMA_HOST', 'https://ollama.com').strip() or 'https://ollama.com'
            ollama_host = ollama_host.rstrip('/')
            ollama_model = os.environ.get('OLLAMA_CHAT_MODEL', 'gpt-oss:120b').strip() or 'gpt-oss:120b'
            ollama_key = os.environ.get('OLLAMA_API_KEY', '').strip()

            headers = {'Content-Type': 'application/json'}
            if ollama_key:
                headers['Authorization'] = f'Bearer {ollama_key}'
            elif ollama_host.startswith('https://ollama.com'):
                return JsonResponse(
                    {'detail': 'Le chatbot IA n’est pas encore configuré. Ajoutez OLLAMA_API_KEY pour activer Ollama Cloud.'},
                    status=503,
                )

            ollama_payload = {
                'model': ollama_model,
                'messages': messages,
                'stream': False,
                'options': {
                    'temperature': 0.35,
                    'num_predict': 140,
                },
            }

            response = urllib.request.urlopen(
                urllib.request.Request(
                    f'{ollama_host}/api/chat',
                    data=json.dumps(ollama_payload).encode('utf-8'),
                    headers=headers,
                    method='POST',
                ),
                timeout=60,
            )
            response_data = json.loads(response.read().decode('utf-8'))
            reply = (
                response_data.get('message', {})
                .get('content', '')
                .strip()
            )
        else:
            api_key = os.environ.get('OPENAI_API_KEY', '').strip()
            if not api_key:
                return JsonResponse(
                    {'detail': 'Le chatbot IA n’est pas encore configuré. Ajoutez OPENAI_API_KEY pour activer OpenAI.'},
                    status=503,
                )

            openai_payload = {
                'model': os.environ.get('OPENAI_CHAT_MODEL', 'gpt-4o-mini'),
                'messages': messages,
                'temperature': 0.35,
                'max_tokens': 140,
            }
            response = urllib.request.urlopen(
                urllib.request.Request(
                    'https://api.openai.com/v1/chat/completions',
                    data=json.dumps(openai_payload).encode('utf-8'),
                    headers={
                        'Content-Type': 'application/json',
                        'Authorization': f'Bearer {api_key}',
                    },
                    method='POST',
                ),
                timeout=30,
            )
            response_data = json.loads(response.read().decode('utf-8'))
            reply = (
                response_data.get('choices', [{}])[0]
                .get('message', {})
                .get('content', '')
                .strip()
            )

        if not reply:
            return JsonResponse({'detail': 'Aucune réponse n’a été générée.'}, status=502)
        _CHATBOT_REPLY_CACHE[cache_key] = {'reply': reply, 'ts': time.time()}
        return JsonResponse({'reply': reply})
    except urllib.error.HTTPError as exc:
        try:
            error_payload = json.loads(exc.read().decode('utf-8'))
            detail = error_payload.get('error', {}).get('message') or 'Erreur du service IA.'
        except Exception:
            detail = 'Erreur du service IA.'
        return JsonResponse({'detail': detail}, status=502)
    except Exception:
        return JsonResponse({'detail': 'Le chatbot IA est momentanément indisponible.'}, status=502)
@csrf_exempt
def admin_branches(request):
    if request.user.role != User.Role.GENERAL_MANAGER:
        return JsonResponse({'detail': 'Accès administrateur refusé.'}, status=403)
    if request.method == 'GET':
        branches = Branch.objects.select_related('sector', 'laboratoire').all()
        return JsonResponse(
            {
                'branches': list(
                    branches.values('id', 'code', 'name', 'sector_id', 'sector__name', 'laboratoire_id', 'laboratoire__name')
                )
            }
        )

    data = json.loads(request.body or '{}')
    code = data.get('code')
    name = str(data.get('name', '')).strip()
    sector_id = data.get('sector_id')
    laboratoire_id = data.get('laboratoire_id')
    if not code or not name or not sector_id:
        return JsonResponse({'detail': 'Code, nom et secteur requis.'}, status=400)

    if Branch.objects.filter(code=code).exists():
        return JsonResponse({'detail': 'Le code de filiale doit être unique.'}, status=400)
    if Branch.objects.filter(name=name, sector_id=sector_id).exists():
        return JsonResponse(
            {'detail': 'Une filiale avec ce nom existe déjà pour ce secteur.'},
            status=400,
        )
    if not Sector.objects.filter(pk=sector_id).exists():
        return JsonResponse({'detail': 'Secteur invalide.'}, status=400)

    try:
        branch = Branch.objects.create(code=code, name=name, sector_id=sector_id, laboratoire_id=laboratoire_id)
    except IntegrityError:
        return JsonResponse(
            {'detail': 'Impossible de créer la filiale. Vérifiez le secteur.'},
            status=400,
        )

    return JsonResponse(
        {
            'id': branch.id,
            'code': branch.code,
            'name': branch.name,
            'sector_id': branch.sector_id,
            'sector_name': branch.sector.name,
            'laboratoire_id': branch.laboratoire_id,
            'laboratoire_name': branch.laboratoire.name if branch.laboratoire else '',
        },
        status=201,
    )


@csrf_exempt
def admin_branch_detail(request, branch_id):
    if request.user.role != User.Role.GENERAL_MANAGER:
        return JsonResponse({'detail': 'Accès administrateur refusé.'}, status=403)
    try:
        branch = Branch.objects.get(pk=branch_id)
    except Branch.DoesNotExist:
        return JsonResponse({'detail': 'Filiale introuvable.'}, status=404)

    if request.method == 'PATCH':
        data = json.loads(request.body or '{}')
        code = data.get('code')
        name = str(data.get('name', '')).strip()
        sector_id = data.get('sector_id')
        laboratoire_id = data.get('laboratoire_id')
        if not code or not name or not sector_id:
            return JsonResponse({'detail': 'Code, nom et secteur requis.'}, status=400)
        if not Sector.objects.filter(pk=sector_id).exists():
            return JsonResponse({'detail': 'Secteur invalide.'}, status=400)

        if Branch.objects.filter(code=code).exclude(pk=branch_id).exists():
            return JsonResponse({'detail': 'Le code de filiale doit être unique.'}, status=400)
        if Branch.objects.filter(name=name, sector_id=sector_id).exclude(pk=branch_id).exists():
            return JsonResponse(
                {'detail': 'Une filiale avec ce nom existe déjà pour ce secteur.'},
                status=400,
            )

        branch.code = code
        branch.name = name
        branch.sector_id = sector_id
        branch.laboratoire_id = laboratoire_id
        try:
            branch.save()
        except IntegrityError:
            return JsonResponse(
                {'detail': 'Impossible de mettre à jour la filiale. Vérifiez le secteur.'},
                status=400,
            )
        sync_branch_users_sector(branch)
        return JsonResponse(
            {
                'id': branch.id,
                'code': branch.code,
                'name': branch.name,
                'sector_id': branch.sector_id,
                'sector_name': branch.sector.name,
                'laboratoire_id': branch.laboratoire_id,
                'laboratoire_name': branch.laboratoire.name if branch.laboratoire else '',
            }
        )

    if request.method == 'DELETE':
        branch.delete()
        return JsonResponse({'id': branch_id, 'deleted': True})

    return JsonResponse({'detail': 'Méthode non autorisée.'}, status=405)


# ---------------------------------------------------------------------------
# Administration — Secteurs
# ---------------------------------------------------------------------------

@csrf_exempt
def admin_sectors(request):
    if request.user.role != User.Role.GENERAL_MANAGER:
        return JsonResponse({'detail': 'Accès administrateur refusé.'}, status=403)
    if request.method == 'GET':
        sectors = Sector.objects.all()
        return JsonResponse({'sectors': list(sectors.values('id', 'name'))})

    data = json.loads(request.body or '{}')
    name = str(data.get('name', '')).strip()
    manager_id = data.get('manager_id')
    if not name or not manager_id:
        return JsonResponse({'detail': 'Nom du secteur et responsable requis.'}, status=400)

    if Sector.objects.filter(name__iexact=name).exists():
        return JsonResponse({'detail': 'Ce secteur existe déjà.'}, status=400)
    if not User.objects.filter(pk=manager_id, role=User.Role.SECTOR_MANAGER).exists():
        return JsonResponse({'detail': 'Responsable invalide.'}, status=400)

    sector = Sector.objects.create(name=name, manager_id=manager_id)
    User.objects.filter(pk=manager_id).update(sector_id=sector.id)
    return JsonResponse(
        {
            'id': sector.id,
            'name': sector.name,
            'manager_id': sector.manager_id,
            'manager_name': f'{sector.manager.first_name} {sector.manager.last_name}'.strip(),
        },
        status=201,
    )


@csrf_exempt
def admin_sector_detail(request, sector_id):
    if request.user.role != User.Role.GENERAL_MANAGER:
        return JsonResponse({'detail': 'Accès administrateur refusé.'}, status=403)
    try:
        sector = Sector.objects.get(pk=sector_id)
    except Sector.DoesNotExist:
        return JsonResponse({'detail': 'Secteur introuvable.'}, status=404)

    if request.method == 'PATCH':
        data = json.loads(request.body or '{}')
        name = str(data.get('name', '')).strip()
        manager_id = data.get('manager_id')
        if not name or not manager_id:
            return JsonResponse({'detail': 'Nom du secteur et responsable requis.'}, status=400)
        if Sector.objects.filter(name__iexact=name).exclude(pk=sector_id).exists():
            return JsonResponse({'detail': 'Ce secteur existe déjà.'}, status=400)
        if not User.objects.filter(pk=manager_id, role=User.Role.SECTOR_MANAGER).exists():
            return JsonResponse({'detail': 'Responsable invalide.'}, status=400)
        previous_manager_id = sector.manager_id
        sector.name = name
        sector.manager_id = manager_id
        sector.save(update_fields=['name', 'manager_id'])
        if previous_manager_id and previous_manager_id != manager_id:
            previous_manager = User.objects.filter(pk=previous_manager_id).first()
            if previous_manager:
                sync_user_sector(previous_manager)
        User.objects.filter(pk=manager_id).update(sector_id=sector.id)
        manager_name = (
            f'{sector.manager.first_name} {sector.manager.last_name}'.strip()
            if sector.manager
            else ''
        )
        return JsonResponse(
            {
                'id': sector.id,
                'name': sector.name,
                'manager_id': sector.manager_id,
                'manager_name': manager_name,
            }
        )

    if request.method == 'DELETE':
        try:
            sector.delete()
        except ProtectedError:
            return JsonResponse(
                {'detail': 'Impossible de supprimer ce secteur car des filiales lui sont rattachées.'},
                status=400,
            )
        return JsonResponse({'id': sector.id, 'deleted': True})

    return JsonResponse({'detail': 'Méthode non autorisée.'}, status=405)


# ---------------------------------------------------------------------------
# Administration — Évaluations (Fact_Evaluation)
# ---------------------------------------------------------------------------

@csrf_exempt
def admin_evaluations(request):
    if request.user.role != User.Role.GENERAL_MANAGER:
        return JsonResponse({'detail': 'Accès administrateur refusé.'}, status=403)

    if request.method == 'GET':
        evaluations = (
            Evaluation.objects.select_related('filiale__sector', 'laboratoire', 'date', 'user')
            .order_by(
                Lower('axe_evaluation'),
                Lower('criteres'),
                Lower('filiale__name'),
                Lower('laboratoire__name'),
                'line_pk',
            )
        )
        return JsonResponse(
            {
                'evaluations': [
                    {
                        'id': int(ev.id) if ev.id else ev.line_pk,
                        'line_pk': ev.line_pk,
                        'filiale_id': ev.filiale_id,
                        'filiale_name': ev.filiale.name if ev.filiale else ev.filiale_name,
                        'filiale_code': ev.filiale.code if ev.filiale else ev.code,
                        'secteur_name': ev.filiale.sector.name if ev.filiale and ev.filiale.sector else '',
                        'laboratoire_id': ev.laboratoire_id,
                        'laboratoire_name': ev.laboratoire.name if ev.laboratoire else '',
                        'date_id': ev.date_id,
                        'mois': ev.date.mois if ev.date else '',
                        'trimestre': ev.date.trimestre if ev.date else '',
                        'annee': ev.date.annee if ev.date else '',
                        'user_id': ev.user_id,
                        'axe_evaluation': ev.axe_evaluation,
                        'criteres': ev.criteres,
                        'note': ev.note,
                        'ponderation': ev.ponderation,
                        'observations': ev.observations,
                        'moy_ponderation': ev.moy_ponderation,
                        'tx_conformite': ev.tx_conformite,
                        'created_at': ev.created_at,
                        'updated_at': ev.updated_at,
                    }
                    for ev in evaluations
                ]
            }
        )

    if request.method != 'POST':
        return JsonResponse({'detail': 'Méthode non autorisée.'}, status=405)

    data = json.loads(request.body or '{}')
    evaluations = data.get('evaluations')
    if not isinstance(evaluations, list) or not evaluations:
        return JsonResponse({'detail': 'Aucune évaluation fournie.'}, status=400)

    saved = []
    created = 0
    updated = 0
    errors = []
    batch_group_id = resolve_evaluation_id()

    def resolve_branch_from_code(raw_code):
        code_value = str(raw_code or '').strip()
        if not code_value or not code_value.isdigit():
            return None
        return Branch.objects.filter(code=int(code_value)).first()

    for index, item in enumerate(evaluations, start=1):
        line_pk = item.get('line_pk')
        requested_group_id = resolve_evaluation_id(item.get('id'), batch_group_id)
        code = str(item.get('code', '')).strip()
        filiale_name = str(item.get('filiale', '')).strip()
        month = str(item.get('month', '')).strip()
        year = str(item.get('year', '')).strip()
        laboratoire_name = str(item.get('laboratoire', '')).strip()
        axe_evaluation = str(item.get('axe_evaluation', '')).strip()
        criteres = str(item.get('criteres', '')).strip()
        note = str(item.get('note', '')).strip()
        ponderation = str(item.get('ponderation', '')).strip()
        observations = str(item.get('observations', '')).strip()

        # Résolution des clés étrangères vers les dimensions
        branch = resolve_branch_from_code(code)
        laboratoire = get_or_create_laboratoire(laboratoire_name) or (branch and branch.laboratoire)
        laboratoire = laboratoire or getattr(request.user, 'branch', None) and request.user.branch.laboratoire
        laboratoire = laboratoire or Laboratoire.objects.first()
        laboratoire = laboratoire or Laboratoire.objects.get_or_create(name='Physicochimique')[0]
        date_dim = get_or_create_date(month, year)

        # Indicateurs calculés
        moy_ponderation = compute_moy_ponderation(ponderation)
        tx_conformite = compute_tx_conformite(note)

        if line_pk:
            evaluation = Evaluation.objects.filter(pk=line_pk).first()
            if not evaluation:
                errors.append(f'Ligne {index} : évaluation introuvable pour la ligne {line_pk}.')
                continue

            if not evaluation.user_id:
                evaluation.user = request.user
            evaluation.filiale = branch
            evaluation.filiale_name = filiale_name
            evaluation.laboratoire = laboratoire
            evaluation.date = date_dim
            evaluation.axe_evaluation = axe_evaluation
            evaluation.criteres = criteres
            evaluation.note = note
            evaluation.ponderation = ponderation
            evaluation.observations = observations
            evaluation.moy_ponderation = moy_ponderation
            evaluation.tx_conformite = tx_conformite
            evaluation.code = code
            if not evaluation.id:
                evaluation.id = requested_group_id
            evaluation.save()
            saved.append(evaluation.id)
            updated += 1
            continue

        # Anti-doublon : recherche par clés naturelles
        evaluation = Evaluation.objects.filter(
            code=code,
            date=date_dim,
            laboratoire=laboratoire,
            axe_evaluation=axe_evaluation,
            criteres=criteres,
        ).first()

        if evaluation:
            evaluation.filiale = branch
            evaluation.filiale_name = filiale_name
            evaluation.note = note
            evaluation.ponderation = ponderation
            evaluation.observations = observations
            evaluation.moy_ponderation = moy_ponderation
            evaluation.tx_conformite = tx_conformite
            if not evaluation.id:
                evaluation.id = requested_group_id
            evaluation.save()
            updated += 1
        else:
            evaluation = Evaluation.objects.create(
                id=requested_group_id,
                filiale=branch,
                filiale_name=filiale_name,
                laboratoire=laboratoire or Laboratoire.objects.get_or_create(name='Physicochimique')[0],
                date=date_dim,
                user=request.user,
                axe_evaluation=axe_evaluation,
                criteres=criteres,
                note=note,
                ponderation=ponderation,
                observations=observations,
                moy_ponderation=moy_ponderation,
                tx_conformite=tx_conformite,
                code=code,
            )
            created += 1
        saved.append(evaluation.id)

    response = {
        'saved': len(saved),
        'created': created,
        'updated': updated,
    }
    if errors:
        response['errors'] = errors
    if saved:
        invalidate_evaluation_response_cache()
    return JsonResponse(response, status=201 if saved else 400)


@csrf_exempt
def admin_evaluation_detail(request, evaluation_id):
    if request.user.role != User.Role.GENERAL_MANAGER:
        return JsonResponse({'detail': 'Accès administrateur refusé.'}, status=403)

    try:
        evaluation = Evaluation.objects.get(pk=evaluation_id)
    except Evaluation.DoesNotExist:
        return JsonResponse({'detail': 'Évaluation introuvable.'}, status=404)

    if request.method == 'PATCH':
        data = json.loads(request.body or '{}')
        note = str(data.get('note', evaluation.note or '')).strip()
        observations = str(data.get('observations', evaluation.observations or '')).strip()

        evaluation.note = note
        evaluation.observations = observations
        # Recalcul des indicateurs à partir des nouvelles valeurs
        evaluation.moy_ponderation = compute_moy_ponderation(evaluation.ponderation)
        evaluation.tx_conformite = compute_tx_conformite(note)
        evaluation.save(
            update_fields=['note', 'observations', 'moy_ponderation', 'tx_conformite', 'updated_at']
        )
        invalidate_evaluation_response_cache()

        return JsonResponse(
            {
                'id': int(evaluation.id) if evaluation.id else evaluation.line_pk,
                'line_pk': evaluation.line_pk,
                'note': evaluation.note,
                'observations': evaluation.observations,
                'moy_ponderation': evaluation.moy_ponderation,
                'tx_conformite': evaluation.tx_conformite,
                'updated_at': evaluation.updated_at,
            }
        )

    if request.method == 'DELETE':
        evaluation.delete()
        invalidate_evaluation_response_cache()
        return JsonResponse({'line_pk': evaluation_id, 'deleted': True})

    return JsonResponse({'detail': 'Méthode non autorisée.'}, status=405)


@csrf_exempt
def user_evaluation_detail(request, evaluation_id):
    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Authentification requise.'}, status=401)

    try:
        evaluation = Evaluation.objects.get(pk=evaluation_id)
    except Evaluation.DoesNotExist:
        return JsonResponse({'detail': 'Évaluation introuvable.'}, status=404)

    is_owner = evaluation.user_id == request.user.id
    is_sector_manager = (
        request.user.role == User.Role.SECTOR_MANAGER
        and hasattr(request.user, 'managed_sector')
        and request.user.managed_sector
        and evaluation.filiale
        and evaluation.filiale.sector == request.user.managed_sector
    )

    if not is_owner and not is_sector_manager:
        return JsonResponse({'detail': 'Accès refusé.'}, status=403)

    if request.method == 'PATCH':
        data = json.loads(request.body or '{}')
        note = str(data.get('note', evaluation.note or '')).strip()
        observations = str(data.get('observations', evaluation.observations or '')).strip()

        evaluation.note = note
        evaluation.observations = observations
        evaluation.moy_ponderation = compute_moy_ponderation(evaluation.ponderation)
        evaluation.tx_conformite = compute_tx_conformite(note)
        evaluation.save(update_fields=['note', 'observations', 'moy_ponderation', 'tx_conformite', 'updated_at'])
        invalidate_evaluation_response_cache()

        return JsonResponse(
            {
                'id': int(evaluation.id) if evaluation.id else evaluation.line_pk,
                'line_pk': evaluation.line_pk,
                'note': evaluation.note,
                'observations': evaluation.observations,
                'moy_ponderation': evaluation.moy_ponderation,
                'tx_conformite': evaluation.tx_conformite,
                'updated_at': evaluation.updated_at,
            }
        )

    if request.method == 'DELETE':
        evaluation.delete()
        invalidate_evaluation_response_cache()
        return JsonResponse({'line_pk': evaluation_id, 'deleted': True})

    return JsonResponse({'detail': 'Méthode non autorisée.'}, status=405)


@csrf_exempt
def user_evaluations_summary(request):
    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Authentification requise.'}, status=401)
    if request.method != 'GET':
        return JsonResponse({'detail': 'Méthode non autorisée.'}, status=405)

    cache_key = _evaluation_cache_key('user_evaluations_summary', request.user, request)
    cached_payload = _get_cached_evaluation_response(cache_key)
    if cached_payload is not None:
        return JsonResponse(cached_payload)

    evaluations = get_scoped_evaluations(request.user)
    payload = {'evaluations': build_evaluation_summaries(evaluations)}
    _set_cached_evaluation_response(cache_key, payload)
    return JsonResponse(payload)


@csrf_exempt
def user_evaluations_session(request):
    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Authentification requise.'}, status=401)
    if request.method != 'GET':
        return JsonResponse({'detail': 'Méthode non autorisée.'}, status=405)

    mois = request.GET.get('mois', '').strip()
    annee = request.GET.get('annee', '').strip()
    filiale_id = request.GET.get('filiale_id', '').strip()
    filiale_name = request.GET.get('filiale_name', '').strip()
    laboratoire_id = request.GET.get('laboratoire_id', '').strip()
    evaluation_id = request.GET.get('id', '').strip() or request.GET.get('evaluation_id', '').strip()

    qs = apply_evaluation_filters(get_scoped_evaluations(request.user), request)

    if evaluation_id:
        return JsonResponse({'evaluations': build_evaluation_session_rows(qs.filter(id=evaluation_id))})

    if mois:
        qs = qs.filter(date__mois__iexact=mois)
    if annee:
        qs = qs.filter(date__annee__iexact=annee)
    if filiale_id and filiale_id.isdigit():
        qs = qs.filter(filiale_id=int(filiale_id))
    elif filiale_name:
        qs = qs.filter(Q(filiale__name__iexact=filiale_name) | Q(filiale_name__iexact=filiale_name))
    if laboratoire_id and laboratoire_id.isdigit():
        qs = qs.filter(laboratoire_id=int(laboratoire_id))

    return JsonResponse({'evaluations': build_evaluation_session_rows(qs)})


@csrf_exempt
def evaluations_summary(request):
    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Authentification requise.'}, status=401)
    if request.method != 'GET':
        return JsonResponse({'detail': 'Méthode non autorisée.'}, status=405)

    cache_key = _evaluation_cache_key('evaluations_summary', request.user, request)
    cached_payload = _get_cached_evaluation_response(cache_key)
    if cached_payload is not None:
        return JsonResponse(cached_payload)

    evaluations = apply_evaluation_filters(get_scoped_evaluations(request.user), request)
    payload = {'evaluations': build_evaluation_summaries(evaluations)}
    _set_cached_evaluation_response(cache_key, payload)
    return JsonResponse(payload)


@csrf_exempt
def user_evaluations_overview(request):
    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Authentification requise.'}, status=401)
    if request.method != 'GET':
        return JsonResponse({'detail': 'Méthode non autorisée.'}, status=405)

    cache_key = _evaluation_cache_key('user_evaluations_overview', request.user, request)
    cached_payload = _get_cached_evaluation_response(cache_key)
    if cached_payload is not None:
        return JsonResponse(cached_payload)

    evaluations = get_scoped_evaluations(request.user)
    payload = build_evaluation_overview(evaluations, request.GET.get('since'))
    _set_cached_evaluation_response(cache_key, payload)
    return JsonResponse(payload)


@csrf_exempt
def evaluations_overview(request):
    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Authentification requise.'}, status=401)
    if request.method != 'GET':
        return JsonResponse({'detail': 'Méthode non autorisée.'}, status=405)

    cache_key = _evaluation_cache_key('evaluations_overview', request.user, request)
    cached_payload = _get_cached_evaluation_response(cache_key)
    if cached_payload is not None:
        return JsonResponse(cached_payload)

    evaluations = apply_evaluation_filters(get_scoped_evaluations(request.user), request)
    payload = build_evaluation_overview(evaluations, request.GET.get('since'))
    _set_cached_evaluation_response(cache_key, payload)
    return JsonResponse(payload)


@csrf_exempt
def evaluations_session(request):
    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Authentification requise.'}, status=401)
    if request.method != 'GET':
        return JsonResponse({'detail': 'Méthode non autorisée.'}, status=405)

    mois = request.GET.get('mois', '').strip()
    annee = request.GET.get('annee', '').strip()
    filiale_id = request.GET.get('filiale_id', '').strip()
    filiale_name = request.GET.get('filiale_name', '').strip()
    laboratoire_id = request.GET.get('laboratoire_id', '').strip()
    evaluation_id = request.GET.get('id', '').strip() or request.GET.get('evaluation_id', '').strip()

    qs = apply_evaluation_filters(get_scoped_evaluations(request.user), request)

    if evaluation_id:
        return JsonResponse({'evaluations': build_evaluation_session_rows(qs.filter(id=evaluation_id))})

    if mois:
        qs = qs.filter(date__mois__iexact=mois)
    if annee:
        qs = qs.filter(date__annee__iexact=annee)
    if filiale_id and filiale_id.isdigit():
        qs = qs.filter(filiale_id=int(filiale_id))
    elif filiale_name:
        qs = qs.filter(Q(filiale__name__iexact=filiale_name) | Q(filiale_name__iexact=filiale_name))
    if laboratoire_id and laboratoire_id.isdigit():
        qs = qs.filter(laboratoire_id=int(laboratoire_id))

    return JsonResponse({'evaluations': build_evaluation_session_rows(qs)})


# ---------------------------------------------------------------------------
# Administration — Utilisateurs
# ---------------------------------------------------------------------------

@csrf_exempt
def admin_users(request):
    if request.user.role != User.Role.GENERAL_MANAGER:
        return JsonResponse({'detail': 'Accès administrateur refusé.'}, status=403)

    if request.method == 'GET':
        users = (
            User.objects.filter(role=User.Role.USER)
            .values(
                'id',
                'email',
                'first_name',
                'last_name',
                'role',
                'branch_id',
                'branch__name',
                'branch__sector__name',
                'sector_id',
                'sector__name',
                'is_active',
            )
            .order_by('email')
        )
        return JsonResponse({'users': list(users)})

    if request.method != 'POST':
        return JsonResponse({'detail': 'Méthode non autorisée.'}, status=405)

    data = json.loads(request.body or '{}')
    email = str(data.get('email', '')).strip()
    password = data.get('password', '')
    first_name = str(data.get('first_name', '')).strip()
    last_name = str(data.get('last_name', '')).strip()
    role = data.get('role', User.Role.USER)
    branch_id = data.get('branch_id')
    managed_sector_id = data.get('managed_sector_id')

    if not email or '@' not in email or not password or len(password) < 8 or not first_name or not last_name:
        return JsonResponse(
            {'detail': 'E-mail, mot de passe, prénom et nom sont requis.'},
            status=400,
        )
    if role not in User.Role.values:
        role = User.Role.USER
    if role == User.Role.USER and not branch_id:
        return JsonResponse({'detail': 'La filiale est requise pour un utilisateur.'}, status=400)
    if role == User.Role.SECTOR_MANAGER and managed_sector_id and not Sector.objects.filter(pk=managed_sector_id).exists():
        return JsonResponse({'detail': 'Secteur invalide.'}, status=400)
    if branch_id and not Branch.objects.filter(pk=branch_id).exists():
        return JsonResponse({'detail': 'Filiale invalide.'}, status=400)
    if User.objects.filter(email=email).exists():
        return JsonResponse({'detail': 'Cet e-mail existe déjà.'}, status=400)
    sector = None
    if role == User.Role.SECTOR_MANAGER and managed_sector_id:
        sector = Sector.objects.get(pk=managed_sector_id)
        if sector.manager_id:
            return JsonResponse({'detail': 'Ce secteur est déjà affecté à un responsable.'}, status=400)
    resolved_sector_id = resolve_user_sector_id(role, branch_id=branch_id, managed_sector_id=managed_sector_id)

    user = User.objects.create_user(
        email,
        password,
        role=role,
        first_name=first_name,
        last_name=last_name,
        branch_id=branch_id if branch_id else None,
        sector_id=resolved_sector_id,
        is_staff=(role == User.Role.GENERAL_MANAGER),
    )
    if role == User.Role.SECTOR_MANAGER and sector:
        sector.manager = user
        sector.save(update_fields=['manager'])

    return JsonResponse(
        {
            'id': user.id,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'role': user.role,
            'branch_id': user.branch_id,
            'branch_name': user.branch.name if user.branch else None,
            'sector_id': user.sector_id,
            'sector_name': get_user_sector_name(user),
            'managed_sector_id': managed_sector_id if role == User.Role.SECTOR_MANAGER else None,
            'managed_sector_name': sector.name if role == User.Role.SECTOR_MANAGER and managed_sector_id else None,
            'is_active': user.is_active,
        },
        status=201,
    )


@csrf_exempt
def admin_user_detail(request, user_id):
    if request.user.role != User.Role.GENERAL_MANAGER:
        return JsonResponse({'detail': 'Accès administrateur refusé.'}, status=403)

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return JsonResponse({'detail': 'Utilisateur introuvable.'}, status=404)

    if request.method == 'PATCH':
        data = json.loads(request.body or '{}')
        email = str(data.get('email', '')).strip()
        first_name = str(data.get('first_name', '')).strip()
        last_name = str(data.get('last_name', '')).strip()
        role = data.get('role', user.role)
        branch_id = data.get('branch_id')
        managed_sector_id = data.get('managed_sector_id')
        password = data.get('password')

        if not email or not first_name or not last_name:
            return JsonResponse({'detail': 'E-mail, prénom et nom sont requis.'}, status=400)
        if role not in User.Role.values:
            return JsonResponse({'detail': 'Rôle invalide.'}, status=400)
        if role == User.Role.USER and not branch_id:
            return JsonResponse({'detail': 'La filiale est requise pour un utilisateur.'}, status=400)
        if role == User.Role.SECTOR_MANAGER and managed_sector_id and not Sector.objects.filter(pk=managed_sector_id).exists():
            return JsonResponse({'detail': 'Secteur invalide.'}, status=400)
        if branch_id and not Branch.objects.filter(pk=branch_id).exists():
            return JsonResponse({'detail': 'Filiale invalide.'}, status=400)
        if User.objects.filter(email=email).exclude(pk=user_id).exists():
            return JsonResponse({'detail': 'Cet e-mail existe déjà.'}, status=400)

        current_sector = getattr(user, 'managed_sector', None)
        sector = None
        if role == User.Role.SECTOR_MANAGER and managed_sector_id:
            sector = Sector.objects.get(pk=managed_sector_id)
            if sector.manager_id and sector.manager_id != user.id:
                return JsonResponse({'detail': 'Ce secteur est déjà affecté à un autre responsable.'}, status=400)
        if role != User.Role.SECTOR_MANAGER and current_sector is not None:
            current_sector.manager = None
            current_sector.save(update_fields=['manager'])
        if role == User.Role.SECTOR_MANAGER and current_sector is not None and (managed_sector_id is None or current_sector.id != managed_sector_id):
            current_sector.manager = None
            current_sector.save(update_fields=['manager'])
        resolved_sector_id = resolve_user_sector_id(role, branch_id=branch_id, managed_sector_id=managed_sector_id)

        user.email = email
        user.first_name = first_name
        user.last_name = last_name
        user.role = role
        user.branch_id = branch_id if branch_id else None
        user.sector_id = resolved_sector_id
        user.is_staff = (role == User.Role.GENERAL_MANAGER)
        if password:
            user.set_password(password)
        user.save()

        if role == User.Role.SECTOR_MANAGER and sector:
            sector.manager = user
            sector.save(update_fields=['manager'])
        elif role == User.Role.SECTOR_MANAGER and managed_sector_id is None:
            if current_sector is not None:
                current_sector.manager = None
                current_sector.save(update_fields=['manager'])

        return JsonResponse(
            {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'role': user.role,
                'branch_id': user.branch_id,
                'branch_name': user.branch.name if user.branch else None,
                'sector_id': user.sector_id,
                'sector_name': get_user_sector_name(user),
                'managed_sector_id': user.managed_sector.id if hasattr(user, 'managed_sector') and user.managed_sector else None,
                'managed_sector_name': user.managed_sector.name if hasattr(user, 'managed_sector') and user.managed_sector else None,
                'is_active': user.is_active,
            }
        )

    if request.method == 'DELETE':
        if user.pk == request.user.pk:
            return JsonResponse({'detail': 'Vous ne pouvez pas supprimer votre propre compte.'}, status=400)
        user.delete()
        return JsonResponse({'id': user.id, 'deleted': True})

    return JsonResponse({'detail': 'Méthode non autorisée.'}, status=405)


@csrf_exempt
def evaluations_list(request):
    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Authentification requise.'}, status=401)

    user = request.user
    if user.role == User.Role.GENERAL_MANAGER:
        evaluations = Evaluation.objects.select_related('filiale__sector', 'laboratoire', 'date', 'user').all()
    elif user.role == User.Role.SECTOR_MANAGER and hasattr(user, 'managed_sector') and user.managed_sector:
        evaluations = Evaluation.objects.select_related('filiale__sector', 'laboratoire', 'date', 'user').filter(
            Q(filiale__sector=user.managed_sector)
            | Q(user__sector=user.managed_sector)
        ).distinct()
    else:
        evaluations = Evaluation.objects.select_related('filiale__sector', 'laboratoire', 'date', 'user').filter(filiale_id=user.branch_id) if user.branch_id else Evaluation.objects.none()

    date_id = request.GET.get('date_id')
    filiale_id = request.GET.get('filiale_id')
    laboratoire_id = request.GET.get('laboratoire_id')
    user_id = request.GET.get('user_id')

    if date_id:
        evaluations = evaluations.filter(date_id=date_id)
    if filiale_id:
        evaluations = evaluations.filter(filiale_id=filiale_id)
    if laboratoire_id:
        evaluations = evaluations.filter(laboratoire_id=laboratoire_id)
    if user_id:
        evaluations = evaluations.filter(user_id=user_id)

    evaluations = evaluations.order_by('-created_at')

    axes = {}
    for ev in evaluations:
        axe = (ev.axe_evaluation or 'Sans axe').strip()
        axes.setdefault(axe, []).append(ev)

    axe_stats = {}
    for axe, evs in axes.items():
        total_weighted = 0.0
        total_weight = 0.0
        for ev in evs:
            try:
                note = float(ev.note or 0)
                weight = float(ev.ponderation or 0)
                total_weighted += note * weight
                total_weight += weight
            except (ValueError, TypeError):
                continue
        moyenne = total_weighted / total_weight if total_weight > 0 else 0.0
        axe_stats[axe] = {
            'moyenne': round(moyenne, 2),
            'conformite': round((moyenne / 20.0) * 100, 2) if moyenne > 0 else 0.0,
        }

    return JsonResponse(
        {
            'evaluations': [
                {
                    'id': int(ev.id) if ev.id else ev.line_pk,
                    'line_pk': ev.line_pk,
                    'filiale_name': ev.filiale.name if ev.filiale else ev.filiale_name,
                    'secteur_name': ev.filiale.sector.name if ev.filiale and ev.filiale.sector else '',
                    'laboratoire_name': ev.laboratoire.name if ev.laboratoire else '',
                    'mois': ev.date.mois if ev.date else '',
                    'trimestre': ev.date.trimestre if ev.date else '',
                    'annee': ev.date.annee if ev.date else '',
                    'axe_evaluation': ev.axe_evaluation,
                    'criteres': ev.criteres,
                    'note': ev.note,
                    'ponderation': ev.ponderation,
                    'moy_ponderation': ev.moy_ponderation,
                    'tx_conformite': ev.tx_conformite,
                    'observations': ev.observations,
                    'user_id': ev.user_id,
                    'user_name': f'{ev.user.first_name} {ev.user.last_name}'.strip() if ev.user else '',
                    'created_at': ev.created_at,
                    'moyenne_axe': axe_stats[(ev.axe_evaluation or 'Sans axe').strip()]['moyenne'],
                    'conformite_axe': axe_stats[(ev.axe_evaluation or 'Sans axe').strip()]['conformite'],
                }
                for ev in evaluations
            ]
        }
    )


@csrf_exempt
def user_evaluations(request):
    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Authentification requise.'}, status=401)

    user = request.user

    if request.method == 'GET':
        evaluations = Evaluation.objects.select_related('filiale__sector', 'laboratoire', 'date', 'user').filter(user=user)
        evaluations = evaluations.order_by('-created_at')

        axes = {}
        for ev in evaluations:
            axe = (ev.axe_evaluation or 'Sans axe').strip()
            axes.setdefault(axe, []).append(ev)

        axe_stats = {}
        for axe, evs in axes.items():
            total_weighted = 0.0
            total_weight = 0.0
            for ev in evs:
                try:
                    note = float(ev.note or 0)
                    weight = float(ev.ponderation or 0)
                    total_weighted += note * weight
                    total_weight += weight
                except (ValueError, TypeError):
                    continue
            moyenne = total_weighted / total_weight if total_weight > 0 else 0.0
            axe_stats[axe] = {
                'moyenne': round(moyenne, 2),
                'conformite': round((moyenne / 20.0) * 100, 2) if moyenne > 0 else 0.0,
            }

        return JsonResponse(
            {
                'evaluations': [
                    {
                        'id': int(ev.id) if ev.id else ev.line_pk,
                        'line_pk': ev.line_pk,
                        'filiale_name': ev.filiale.name if ev.filiale else ev.filiale_name,
                        'secteur_name': ev.filiale.sector.name if ev.filiale and ev.filiale.sector else '',
                        'laboratoire_name': ev.laboratoire.name if ev.laboratoire else '',
                        'mois': ev.date.mois if ev.date else '',
                        'trimestre': ev.date.trimestre if ev.date else '',
                        'annee': ev.date.annee if ev.date else '',
                        'axe_evaluation': ev.axe_evaluation,
                        'criteres': ev.criteres,
                        'note': ev.note,
                        'ponderation': ev.ponderation,
                        'moy_ponderation': ev.moy_ponderation,
                        'tx_conformite': ev.tx_conformite,
                        'observations': ev.observations,
                        'user_id': ev.user_id,
                        'user_name': f'{ev.user.first_name} {ev.user.last_name}'.strip() if ev.user else '',
                        'created_at': ev.created_at,
                        'moyenne_axe': axe_stats[(ev.axe_evaluation or 'Sans axe').strip()]['moyenne'],
                        'conformite_axe': axe_stats[(ev.axe_evaluation or 'Sans axe').strip()]['conformite'],
                    }
                    for ev in evaluations
                ]
            }
        )

    if request.method != 'POST':
        return JsonResponse({'detail': 'Méthode non autorisée.'}, status=405)

    data = json.loads(request.body or '{}')
    evaluations_data = data.get('evaluations')
    if isinstance(evaluations_data, list) and evaluations_data:
        saved = []
        created = 0
        updated = 0
        errors = []
        batch_group_id = resolve_evaluation_id()

        def resolve_branch_from_code(raw_code):
            code_value = str(raw_code or '').strip()
            if not code_value or not code_value.isdigit():
                return None
            return Branch.objects.filter(code=int(code_value)).first()

        for index, item in enumerate(evaluations_data, start=1):
            line_pk = item.get('line_pk')
            requested_group_id = resolve_evaluation_id(item.get('id'), batch_group_id)
            code = str(item.get('code', '')).strip()
            filiale_name = str(item.get('filiale', '')).strip()
            month = str(item.get('month', '')).strip()
            year = str(item.get('year', '')).strip()
            laboratoire_name = str(item.get('laboratoire', '')).strip()
            axe_evaluation = str(item.get('axe_evaluation', '')).strip()
            criteres = str(item.get('criteres', '')).strip()
            note = str(item.get('note', '')).strip()
            ponderation = str(item.get('ponderation', '')).strip()
            observations = str(item.get('observations', '')).strip()

            branch = resolve_branch_from_code(code)
            laboratoire = get_or_create_laboratoire(laboratoire_name) or (branch and branch.laboratoire)
            laboratoire = laboratoire or getattr(user, 'branch', None) and user.branch.laboratoire
            laboratoire = laboratoire or Laboratoire.objects.first()
            laboratoire = laboratoire or Laboratoire.objects.get_or_create(name='Physicochimique')[0]
            date_dim = get_or_create_date(month, year)
            moy_ponderation = compute_moy_ponderation(ponderation)
            tx_conformite = compute_tx_conformite(note)

            if line_pk:
                evaluation = Evaluation.objects.filter(pk=line_pk).first()
                if not evaluation:
                    errors.append(f'Ligne {index} : évaluation introuvable pour la ligne {line_pk}.')
                    continue

                if not evaluation.user_id:
                    evaluation.user = user
                evaluation.filiale = branch
                evaluation.filiale_name = filiale_name
                evaluation.laboratoire = laboratoire
                evaluation.date = date_dim
                evaluation.axe_evaluation = axe_evaluation
                evaluation.criteres = criteres
                evaluation.note = note
                evaluation.ponderation = ponderation
                evaluation.observations = observations
                evaluation.moy_ponderation = moy_ponderation
                evaluation.tx_conformite = tx_conformite
                evaluation.code = code
                if not evaluation.id:
                    evaluation.id = requested_group_id
                evaluation.save()
                saved.append(evaluation.id)
                updated += 1
                continue

            evaluation = Evaluation.objects.create(
                id=requested_group_id,
                filiale=branch,
                filiale_name=filiale_name,
                laboratoire=laboratoire or Laboratoire.objects.get_or_create(name='Physicochimique')[0],
                date=date_dim,
                user=user,
                axe_evaluation=axe_evaluation,
                criteres=criteres,
                note=note,
                ponderation=ponderation,
                observations=observations,
                moy_ponderation=moy_ponderation,
                tx_conformite=tx_conformite,
                code=code,
            )
            saved.append(evaluation.id)
            created += 1

        response = {
            'saved': len(saved),
            'created': created,
            'updated': updated,
        }
        if errors:
            response['errors'] = errors
        if saved:
            invalidate_evaluation_response_cache()
        return JsonResponse(response, status=201 if saved else 400)

    evaluation_data = data.get('evaluation') or data
    month = str(evaluation_data.get('month', '')).strip()
    year = str(evaluation_data.get('year', '')).strip()
    filiale_name = str(evaluation_data.get('filiale', '')).strip()
    code = str(evaluation_data.get('code', '')).strip()
    laboratoire_name = str(evaluation_data.get('laboratoire', '')).strip()
    axe_evaluation = str(evaluation_data.get('axe_evaluation', '')).strip()
    criteres = str(evaluation_data.get('criteres', '')).strip()
    note = str(evaluation_data.get('note', '')).strip()
    ponderation = str(evaluation_data.get('ponderation', '')).strip()
    observations = str(evaluation_data.get('observations', '')).strip()

    branch = None
    if code and code.isdigit():
        branch = Branch.objects.filter(code=int(code)).first()

    laboratoire = get_or_create_laboratoire(laboratoire_name) or (branch and branch.laboratoire)
    laboratoire = laboratoire or getattr(user, 'branch', None) and user.branch.laboratoire
    laboratoire = laboratoire or Laboratoire.objects.first()
    laboratoire = laboratoire or Laboratoire.objects.get_or_create(name='Physicochimique')[0]
    date_dim = get_or_create_date(month, year)
    requested_group_id = resolve_evaluation_id(evaluation_data.get('id'))

    evaluation = Evaluation.objects.create(
        id=requested_group_id,
        filiale=branch,
        filiale_name=filiale_name,
        laboratoire=laboratoire or Laboratoire.objects.get_or_create(name='Physicochimique')[0],
        date=date_dim,
        user=user,
        axe_evaluation=axe_evaluation,
        criteres=criteres,
        note=note,
        ponderation=ponderation,
        observations=observations,
        moy_ponderation=compute_moy_ponderation(ponderation),
        tx_conformite=compute_tx_conformite(note),
        code=code,
    )
    invalidate_evaluation_response_cache()

    return JsonResponse(
        {
            'id': int(evaluation.id) if evaluation.id else evaluation.line_pk,
            'line_pk': evaluation.line_pk,
            'filiale_name': evaluation.filiale.name if evaluation.filiale else evaluation.filiale_name,
            'secteur_name': evaluation.filiale.sector.name if evaluation.filiale and evaluation.filiale.sector else '',
            'laboratoire_name': evaluation.laboratoire.name if evaluation.laboratoire else '',
            'mois': evaluation.date.mois if evaluation.date else '',
            'trimestre': evaluation.date.trimestre if evaluation.date else '',
            'annee': evaluation.date.annee if evaluation.date else '',
            'axe_evaluation': evaluation.axe_evaluation,
            'criteres': evaluation.criteres,
            'note': evaluation.note,
            'ponderation': evaluation.ponderation,
            'moy_ponderation': evaluation.moy_ponderation,
            'tx_conformite': evaluation.tx_conformite,
            'observations': evaluation.observations,
            'user_id': evaluation.user_id,
            'user_name': f'{evaluation.user.first_name} {evaluation.user.last_name}'.strip() if evaluation.user else '',
            'created_at': evaluation.created_at,
        },
        status=201,
    )


@csrf_exempt
def admin_toggle_user(request, user_id):
    if request.method != 'POST' or not request.user.is_staff:
        return JsonResponse({'detail': 'Accès administrateur refusé.'}, status=403)
    user = User.objects.get(pk=user_id)
    if user.pk == request.user.pk:
        return JsonResponse({'detail': 'Vous ne pouvez pas désactiver votre propre compte.'}, status=400)
    user.is_active = not user.is_active
    user.save(update_fields=['is_active'])
    return JsonResponse({'id': user.id, 'is_active': user.is_active})


@csrf_exempt
def admin_branch_change_sector(request, branch_id):
    if request.user.role != User.Role.GENERAL_MANAGER:
        return JsonResponse({'detail': 'Accès administrateur refusé.'}, status=403)

    if request.method != 'POST':
        return JsonResponse({'detail': 'Méthode non autorisée.'}, status=405)

    try:
        branch = Branch.objects.get(pk=branch_id)
    except Branch.DoesNotExist:
        return JsonResponse({'detail': 'Filiale introuvable.'}, status=404)

    data = json.loads(request.body or '{}')
    sector_id = data.get('sector_id')
    if not sector_id:
        return JsonResponse({'detail': 'Secteur requis.'}, status=400)

    try:
        sector = Sector.objects.get(pk=sector_id)
    except Sector.DoesNotExist:
        return JsonResponse({'detail': 'Secteur invalide.'}, status=400)

    affected_users = User.objects.filter(branch=branch).count()
    branch.sector = sector
    branch.save(update_fields=['sector'])
    sync_branch_users_sector(branch)

    return JsonResponse({
        'id': branch.id,
        'code': branch.code,
        'name': branch.name,
        'sector_id': branch.sector_id,
        'sector_name': branch.sector.name,
        'affected_users': affected_users,
    })


@csrf_exempt
def admin_laboratoires(request):
    if request.user.role != User.Role.GENERAL_MANAGER:
        return JsonResponse({'detail': 'Accès administrateur refusé.'}, status=403)

    if request.method == 'GET':
        laboratoires = Laboratoire.objects.all().order_by('name')
        return JsonResponse({'laboratoires': list(laboratoires.values('id', 'name'))})

    if request.method != 'POST':
        return JsonResponse({'detail': 'Méthode non autorisée.'}, status=405)

    data = json.loads(request.body or '{}')
    name = str(data.get('name', '')).strip()

    if not name:
        return JsonResponse({'detail': 'Le nom du laboratoire est requis.'}, status=400)

    if Laboratoire.objects.filter(name__iexact=name).exists():
        return JsonResponse({'detail': 'Ce laboratoire existe déjà.'}, status=400)

    laboratoire = Laboratoire.objects.create(name=name)
    return JsonResponse({'id': laboratoire.id, 'name': laboratoire.name}, status=201)


@csrf_exempt
def admin_laboratoire_detail(request, laboratoire_id):
    if request.user.role != User.Role.GENERAL_MANAGER:
        return JsonResponse({'detail': 'Accès administrateur refusé.'}, status=403)

    try:
        laboratoire = Laboratoire.objects.get(pk=laboratoire_id)
    except Laboratoire.DoesNotExist:
        return JsonResponse({'detail': 'Laboratoire introuvable.'}, status=404)

    if request.method == 'PATCH':
        data = json.loads(request.body or '{}')
        name = str(data.get('name', '')).strip()

        if not name:
            return JsonResponse({'detail': 'Le nom du laboratoire est requis.'}, status=400)

        if Laboratoire.objects.filter(name__iexact=name).exclude(pk=laboratoire_id).exists():
            return JsonResponse({'detail': 'Ce laboratoire existe déjà.'}, status=400)

        laboratoire.name = name
        laboratoire.save(update_fields=['name'])
        return JsonResponse({'id': laboratoire.id, 'name': laboratoire.name})

    if request.method == 'DELETE':
        laboratoire.delete()
        return JsonResponse({'id': laboratoire_id, 'deleted': True})

    return JsonResponse({'detail': 'Méthode non autorisée.'}, status=405)


@csrf_exempt
def user_profile(request):
    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Authentification requise.'}, status=401)

    user = request.user

    if request.method == 'GET':
        return JsonResponse({
            'id': user.id,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'role': user.role,
            'branch_id': user.branch_id,
            'branch_code': user.branch.code if user.branch else None,
            'branch_name': user.branch.name if user.branch else '',
            'sector_name': get_user_sector_name(user),
            'avatar': user.avatar.url if user.avatar else '',
        })

    if request.method != 'POST':
        return JsonResponse({'detail': 'Méthode non autorisée.'}, status=405)

    if request.content_type and 'multipart/form-data' in request.content_type:
        first_name = str(request.POST.get('first_name', user.first_name or '')).strip()
        last_name = str(request.POST.get('last_name', user.last_name or '')).strip()
        new_email = str(request.POST.get('email', user.email or '')).strip()
        avatar_file = request.FILES.get('avatar')

        if new_email and new_email != user.email:
            if User.objects.filter(email=new_email).exclude(pk=user.pk).exists():
                return JsonResponse({'detail': 'Cet e-mail est déjà utilisé.'}, status=400)
            user.email = new_email

        user.first_name = first_name
        user.last_name = last_name

        if avatar_file:
            user.avatar = avatar_file

        user.save(update_fields=['first_name', 'last_name', 'email', 'avatar'] if avatar_file else ['first_name', 'last_name', 'email'])
        return JsonResponse({
            'id': user.id,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'role': user.role,
            'branch_id': user.branch_id,
            'branch_code': user.branch.code if user.branch else None,
            'branch_name': user.branch.name if user.branch else '',
            'sector_name': get_user_sector_name(user),
            'avatar': user.avatar.url if user.avatar else '',
        })

    data = json.loads(request.body or '{}')
    user.first_name = str(data.get('first_name', user.first_name or '')).strip()
    user.last_name = str(data.get('last_name', user.last_name or '')).strip()
    new_email = str(data.get('email', user.email or '')).strip()
    if new_email and new_email != user.email:
        if User.objects.filter(email=new_email).exclude(pk=user.pk).exists():
            return JsonResponse({'detail': 'Cet e-mail est déjà utilisé.'}, status=400)
        user.email = new_email
    user.save(update_fields=['first_name', 'last_name', 'email'])
    return JsonResponse({
        'id': user.id,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'role': user.role,
        'branch_id': user.branch_id,
        'branch_code': user.branch.code if user.branch else None,
        'branch_name': user.branch.name if user.branch else '',
        'sector_name': get_user_sector_name(user),
        'avatar': user.avatar.url if user.avatar else '',
    })


@csrf_exempt
def user_password(request):
    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Authentification requise.'}, status=401)

    if request.method != 'POST':
        return JsonResponse({'detail': 'Méthode non autorisée.'}, status=405)

    data = json.loads(request.body or '{}')
    current_password = str(data.get('current_password', '')).strip()
    new_password = str(data.get('new_password', '')).strip()

    if not current_password or not new_password:
        return JsonResponse({'detail': 'Mot de passe actuel et nouveau mot de passe requis.'}, status=400)

    if not request.user.check_password(current_password):
        return JsonResponse({'detail': 'Mot de passe actuel incorrect.'}, status=400)

    request.user.set_password(new_password)
    request.user.save(update_fields=['password'])
    return JsonResponse({'detail': 'Mot de passe modifié avec succès.'})


@csrf_exempt
def checklist_template(request):
    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Authentification requise.'}, status=401)

    file_path = BASE_DIR / 'frontend' / 'public' / 'stagaire labo.xlsx'
    if not file_path.exists():
        return JsonResponse({'detail': 'Fichier Excel introuvable.'}, status=404)

    with open(file_path, 'rb') as f:
        data = f.read()

    response = HttpResponse(data, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="stagaire_labo.xlsx"'
    return response


@csrf_exempt
def ml_predict(request):
    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Authentification requise.'}, status=401)
    if request.user.role != User.Role.GENERAL_MANAGER:
        return JsonResponse({'detail': 'Accès administrateur requis.'}, status=403)

    if request.method != 'POST':
        return JsonResponse({'detail': 'Méthode non autorisée.'}, status=405)

    data = json.loads(request.body or '{}')
    evaluations = data.get('evaluations') or data.get('rows') or []
    if not isinstance(evaluations, list) or not evaluations:
        return JsonResponse({'detail': 'Aucune évaluation fournie pour la prédiction.'}, status=400)

    try:
        payload = predict_evaluations(evaluations, request.user)
        return JsonResponse(payload)
    except ModelInferenceError as exc:
        return JsonResponse({'detail': str(exc)}, status=503)
    except Exception as exc:  # noqa: BLE001
        return JsonResponse({'detail': f'Erreur pendant la prédiction IA: {exc}'}, status=500)


@csrf_exempt
def ml_status(request):
    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Authentification requise.'}, status=401)
    if request.user.role != User.Role.GENERAL_MANAGER:
        return JsonResponse({'detail': 'Accès administrateur requis.'}, status=403)
    if request.method != 'GET':
        return JsonResponse({'detail': 'Méthode non autorisée.'}, status=405)

    return JsonResponse(get_backend_mlops_status())
