import { AfterViewInit, ChangeDetectorRef, Component, NgZone, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { finalize, timeout } from 'rxjs/operators';
import * as XLSX from 'xlsx';

type ChecklistCriterion = {
  text: string;
  weight: number;
  note?: string;
  obs?: string;
};

type ChecklistAxe = {
  id: number;
  title: string;
  criteria: ChecklistCriterion[];
  collapsed?: boolean;
};

const ISO_17025_CHECKLIST: ChecklistAxe[] = [
  {
    id: 1,
    title: "Infrastructure et environnement de travail",
    criteria: [
      { text: "Organisation et séparation adéquate des zones de travail afin d'éviter toute contamination, confusion ou altération des résultats (marche en avant, présence d'affichage signalétique)", weight: 2 },
      { text: "Conditions environnementales maîtrisées et surveillées : température, humidité, propreté, ventilation, éclairage, sécurité", weight: 2 },
      { text: "Contrôle des accès aux zones sensibles et sécurité du laboratoire", weight: 2 },
      { text: "Disponibilité des consignes de sécurité, plans d'urgence et signalétique", weight: 2 },
    ],
  },
  {
    id: 2,
    title: "Management documentaire et maîtrise des méthodes",
    criteria: [
      { text: "Disponibilité des méthodes d'analyse validées et à jour", weight: 3 },
      { text: "Maîtrise des documents et enregistrements (version, archivage, diffusion)", weight: 3 },
      { text: "Disponibilité des plans de contrôle et instructions de travail", weight: 2 },
      { text: "Application des plans d'analyse et respect du plan de contrôle", weight: 2 },
      { text: "Gestion des modifications documentaires et approbation des documents", weight: 2 },
    ],
  },
  {
    id: 3,
    title: "Échantillonnage, traçabilité et intégrité des données",
    criteria: [
      { text: "Procédures d'échantillonnage maîtrisées et documentées", weight: 3 },
      { text: "Identification traçabilité complète des échantillons, des analyses", weight: 3 },
      { text: "Conditions de transport, stockage et conservation maîtrisées", weight: 2 },
      { text: "Traçabilité et conservation des analyses laboratoire : fiche paillasse, fiche intervention sur instrument, vérification interne…", weight: 3 },
    ],
  },
  {
    id: 4,
    title: "Équipements et métrologie",
    criteria: [
      { text: "Inventaire des équipements / réactifs disponible et à jour", weight: 2 },
      { text: "Maintenance préventive et corrective documentée : CTA, hotte chimique / flux laminaire", weight: 2 },
      { text: "Étalonnage et vérification métrologique réalisés selon planning", weight: 4 },
      { text: "Statut métrologique identifiable sur chaque équipement", weight: 2 },
      { text: "Gestion des pannes et impact sur la validité / fiabilité des résultats évalué", weight: 2 },
    ],
  },
  {
    id: 5,
    title: "Compétence du personnel",
    criteria: [
      { text: "Définition des fonctions et responsabilités du personnel laboratoire", weight: 2 },
      { text: "Qualification et habilitation du personnel documentées : disponibilité des compétences, polyvalence, niveau de formation", weight: 3 },
      { text: "Évaluation des compétences techniques (aptitude du personnel laboratoire aux analyses réalisées : audit protocole)", weight: 5 },
      { text: "Évaluation périodique des compétences techniques", weight: 2 },
      { text: "Plan de formation et suivi des compétences disponible (sensibilisation aux exigences qualité et impartialité)", weight: 2 },
    ],
  },
  {
    id: 6,
    title: "Assurance qualité des résultats",
    criteria: [
      { text: "Respect du plan de CQ physicochimique et microbiologique : mise en œuvre des contrôles qualité internes (CQI)", weight: 4 },
      { text: "Comparaisons des résultats avec des résultats de laboratoires accrédités (validation des résultats de contrôle)", weight: 3 },
      { text: "Surveillance des tendances et exploitation statistique des résultats", weight: 2 },
      { text: "Disponibilité et mise à jour des instructions laboratoire, plan de contrôle", weight: 2 },
    ],
  },
  {
    id: 7,
    title: "Exploitation laboratoire et gestion des réactifs, consommables et stocks",
    criteria: [
      { text: "Identification et conformité des réactifs chimiques", weight: 2 },
      { text: "Conditions de stockage adaptées et surveillées : bonne gestion des réactifs dangereux et application des normes de BP de stockage dans un laboratoire de CQ", weight: 2 },
      { text: "Gestion des dates de péremption et FEFO / FIFO", weight: 2 },
      { text: "Gestion des stocks assurée systématiquement : absence de réactifs avec DLC périmées", weight: 1 },
    ],
  },
  {
    id: 8,
    title: "Sécurité et gestion des déchets",
    criteria: [
      { text: "Respect des règles HSE et port des EPI", weight: 2 },
      { text: "Gestion des déchets chimiques et biologiques conforme", weight: 2 },
      { text: "Disponibilité des FDS et gestion des produits dangereux", weight: 2 },
      { text: "Procédures de gestion des incidents et situations d'urgence", weight: 2 },
    ],
  },
  {
    id: 9,
    title: "Prestations externes et sous-traitance",
    criteria: [
      { text: "Évaluation et suivi des laboratoires sous-traitants", weight: 3 },
      { text: "Vérification des accréditations et compétences des prestataires", weight: 3 },
      { text: "Maîtrise du transport des échantillons externalisés", weight: 2 },
    ],
  },
  {
    id: 10,
    title: "Gestion des non-conformités et amélioration",
    criteria: [
      { text: "Détection et traitement des non-conformités (plan d'action)", weight: 2 },
      { text: "Mise en œuvre des actions correctives et suivi d'efficacité", weight: 1 },
    ],
  },
  {
    id: 11,
    title: "Axe documentaire / QUALIPRO",
    criteria: [
      { text: "Exploitation du système, suivi des indicateurs, reporting, gestion documentaire et suivi des plans d'action", weight: 1 },
    ],
  },
  {
    id: 12,
    title: "Fiabilité des données exportées",
    criteria: [
      { text: "Fiabilité des données exportées", weight: 5 },
    ],
  },
  {
    id: 13,
    title: "Respect de délais de l'envoi",
    criteria: [
      { text: "Respect de délais de l'envoi", weight: 5 },
    ],
  }
];

type AdminUser = {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
  branch_id: number | null;
  branch__name?: string | null;
  branch__sector__name?: string | null;
  managed_sector_id?: number | null;
  managed_sector__name?: string | null;
  is_active: boolean;
  date_joined?: string | null;
};

type ScopeSector = {
  id: number;
  name: string;
  manager_id: number | null;
  manager__first_name?: string | null;
  manager__last_name?: string | null;
};

type ScopeBranch = {
  id: number;
  code: number;
  name: string;
  sector_id: number;
  sector__name: string;
  laboratoire_id: number | null;
  laboratoire__name: string;
};

type ScopeResponse = {
  role: string;
  users?: AdminUser[];
  sectorManagers?: AdminUser[];
  sectors: ScopeSector[];
  branches: ScopeBranch[];
  me?: {
    id: number;
    first_name: string;
    last_name: string;
    email: string;
    branch_id: number | null;
    branch_code?: string | number | null;
    branch__name?: string | null;
    branch__sector__name?: string | null;
    managed_sector_id?: number | null;
    managed_sector__name?: string | null;
    avatar?: string | null;
  };
};

type EvaluationRow = {
  id?: number | null;
  line_pk?: number | null;
  month: string;
  year: string;
  trimestre?: string;
  filiale_id?: number | null;
  filiale: string;
  filiale_name?: string;
  filiale_code?: string | number | null;
  secteur_name?: string;
  manager_name?: string;
  code: string;
  laboratoire: string;
  laboratoire_name?: string;
  axe_evaluation: string;
  criteres: string;
  note: string;
  ponderation: string;
  moy_ponderation?: string;
  tx_conformite?: string;
  observations: string;
  user_id?: number | null;
  user_name?: string;
  moyenne_axe?: number | null;
  conformite_axe?: number | null;
  isNew?: boolean;
  isSaving?: boolean;
  isDeleting?: boolean;
  editing?: boolean;
};

type UserEvaluationSummary = {
  id: number;
  line_pk?: number | null;
  periode: string;
  filiale_name: string;
  secteur_name: string;
  manager_name?: string;
  user_name: string;
  note_moyenne: number | string;
  min_note?: number | string | null;
  max_note?: number | string | null;
  conformite_globale: number | string;
  mois?: number | string;
  annee?: number | string;
  date_id?: number | string;
  filiale_id?: number | string;
  sector_id?: number | string;
  manager_id?: number | string;
  laboratoire_id?: number | string;
  laboratoire_name?: string;
  user_id?: number | string;
  created_at?: string | null;
};

type MlPredictionRow = {
  row_index: number;
  axe_evaluation: string;
  criteres: string;
  ponderation_num: number;
  predicted_note: number;
  predicted_level: string;
  predicted_non_conforme: boolean;
  probability_non_conformite: number | null;
  actual_note?: number | null;
  actual_non_conforme?: boolean | null;
};

type MlPredictionResponse = {
  summary: {
    threshold_non_conformite: number;
    predicted_average_note: number;
    predicted_conformity_pct: number;
    predicted_non_conformities: number;
    total_rows: number;
    best_models: {
      classification: string;
      regression: string;
    };
  };
  rows: MlPredictionRow[];
  top_risks: MlPredictionRow[];
};

type MlopsArtifact = {
  path: string;
  exists: boolean;
  size_bytes?: number;
  updated_at?: string;
  sha256?: string | null;
};

type MlopsRegistryEntry = {
  objective_name: string;
  task_type: string;
  current_run_id: string;
  promoted_model_name: string;
  promoted_metrics: Record<string, string | number | null>;
  artifact?: MlopsArtifact;
  base_rows: number;
  augmented_rows: number;
  training_config?: Record<string, any>;
  runtime_environment?: Record<string, string | number>;
  latest_top_models?: Array<Record<string, string | number | null>>;
  latest_data_summary?: Record<string, string | number | boolean | null>;
  updated_at?: string;
};

type MlopsRun = {
  run_id: string;
  objective_name: string;
  task_type: string;
  started_at: string;
  status: string;
  best_model_name: string;
  best_metrics: Record<string, string | number | null>;
  base_rows: number;
  augmented_rows: number;
};

type MlopsStatusResponse = {
  updated_at: string | null;
  registry: Record<string, MlopsRegistryEntry>;
  recent_runs: Record<string, MlopsRun[]>;
  artifacts: Record<string, MlopsArtifact>;
  paths?: Record<string, string>;
  monitoring?: {
    health_endpoint: string;
    metrics_endpoint: string;
    prometheus_url: string;
    grafana_url: string;
    mlflow_url: string;
  };
};

type ChecklistItem = {
  axe: string;
  critere: string;
  ponderation: string;
  note: string;
  observations: string;
  filiale: string;
  code: string;
  laboratoire: string;
};

type EvaluationAxisGroup = {
  axis: string;
  rows: EvaluationRow[];
  total: number;
  existingCount: number;
  newCount: number;
};

type ChatbotMessage = {
  role: 'user' | 'assistant' | 'system';
  text: string;
  createdAt: string;
};

type BranchMapLocation = {
  sector: string;
  branch: string;
  longitude: number;
  latitude: number;
};

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './app.html',
  styleUrl: './app.css'
})
export class App implements AfterViewInit, OnInit {
  mode: 'login' | 'register' = 'login';
  email = '';
  password = '';
  firstName = '';
  lastName = '';
  role = 'user';
  userFirstName = '';
  userLastName = '';
  userRole = '';
  adminSection: 'home' | 'branches' | 'sectors' | 'users' | 'managers' | 'evaluations' | 'laboratories' | 'ai' = 'home';
  aiWorkspaceMode: 'predict' | 'improve' = 'predict';
  adminUserFilter: 'all' | 'user' | 'sector_manager' = 'all';
  userSection: 'home' | 'profile' | 'secteur' | 'evaluations' | 'sector_users' = 'home';
  branchSearch = '';
  userSearch = '';
  laboratorySearch = '';
  userBranchName = '';
  userBranchCode: string | number | null = null;
  userSectorName = '';
  sectorUsers: Array<{ id: number; email: string; first_name: string; last_name: string; branch__name?: string | null; branch__sector__name?: string | null }> = [];
  sectorUserSearch = '';

  branches: Array<{ id: number; code: number; name: string; sector: string; sectorId: number; laboratoireId: number | null; laboratoireName: string }> = [];
  laboratories: Array<{ id: number; name: string }> = [];

  branchForm: { id: number | null; code: number | null; name: string; sectorId: number | null; laboratoireId: number | null } = {
    id: null,
    code: null,
    name: '',
    sectorId: null,
    laboratoireId: null,
  };
  isBranchEditing = false;
  sectorChangeBranchId: number | null = null;
  sectorChangeSectorId: number | null = null;
  sectorSearch = '';
  sectors: Array<{ id: number; name: string; managerId: number | null; managerName: string }> = [];
  users: AdminUser[] = [];
  sectorManagers: AdminUser[] = [];
  userForm: { id: number | null; email: string; first_name: string; last_name: string; password: string; role: string; branch_id: number | null; managed_sector_id: number | null } = {
    id: null,
    email: '',
    first_name: '',
    last_name: '',
    password: '',
    role: 'sector_manager',
    branch_id: null,
    managed_sector_id: null,
  };
  sectorForm: { id: number | null; name: string; managerId: number | null } = {
    id: null,
    name: '',
    managerId: null,
  };
  isSectorEditing = false;
  isUserEditing = false;
  laboratoryForm: { id: number | null; name: string } = {
    id: null,
    name: '',
  };
  isLaboratoryEditing = false;
  currentUserId: number | null = null;
  userEmail = '';
  userAvatar = '';
  avatarFile: File | null = null;
  isProfileEditing = false;
  showPasswordForm = false;
  currentPassword = '';
  newPassword = '';
  profileError = '';
  profileSuccess = '';
  passwordError = '';
  passwordSuccess = '';
  userEvaluationList: UserEvaluationSummary[] = [];
  userEvaluationListLoading = false;
  userEvaluationSearch = '';
  selectedEvaluation: EvaluationRow[] = [];
  selectedEvaluationTitle = '';
  isEvaluationDetailMode = false;
  isEvaluationFormMode = false;
  readonly isoChecklistData: ChecklistAxe[] = ISO_17025_CHECKLIST;
  checklistFormData: { note: string; observation: string }[][] = [];
  readonly roleOptions = [
    { value: 'user', label: 'Utilisateur' },
    { value: 'sector_manager', label: 'Responsable de secteur' },
    { value: 'general_manager', label: 'Responsable général (administrateur)' },
  ];
  message = '';
  error = '';
  connected = false;
  showPassword = false;
  isLoadingScope = false;
  evaluationFileName = '';
  evaluationError = '';
  evaluationSuccess = '';
  evaluationSaveMessage = '';
  evaluationSaveError = '';
  mlPredictionLoading = false;
  mlPredictionError = '';
  checklistPrediction: MlPredictionResponse | null = null;
  selectedEvaluationPrediction: MlPredictionResponse | null = null;
  mlopsLoading = false;
  mlopsError = '';
  mlopsStatus: MlopsStatusResponse | null = null;
  adminNotificationCount = 0;
  adminUserNotificationCount = 0;
  private adminNotificationRefreshLoading = false;
  evaluations: EvaluationRow[] = [];
  evaluationSummaries: UserEvaluationSummary[] = [];
  evaluationOverview = {
    session_count: 0,
    row_count: 0,
    latest_created_at: null as string | null,
    new_session_count: 0,
  };
  evaluationSearch = '';
  evaluationDateFilter: string = '';
  evaluationSectorFilter: number | null = null;
  evaluationManagerFilter: number | null = null;
  evaluationFilialeFilter: number | null = null;
  evaluationLaboratoireFilter: string = '';
  evaluationUserFilter: number | null = null;
  evaluationDates: string[] = [];
  evaluationLaboratoires: string[] = [];
  evaluationManagers: Array<{ id: number; name: string }> = [];
  pendingDetailPdfExport = false;
  pendingDetailEditMode = false;
  isAuthSubmitting = false;
  isEvaluationLoading = false;
  evaluationOverviewLoading = false;
  adminFormSaving = false;
  profileSaving = false;
  passwordSaving = false;
  evaluationSummariesLoaded = false;
  evaluationSummariesStale = true;
  evaluationOverviewLoaded = false;
  evaluationOverviewStale = true;
  evaluationPage = 1;
  readonly evaluationPageSize = 25;
  userEvaluationListLoaded = false;
  userEvaluationListStale = true;
  laboratoriesLoaded = false;
  scopeDataLoaded = false;
  scopeDataLoading = false;
  toastMessage = '';
  toastType: 'success' | 'error' | 'info' = 'success';
  isDarkMode = false;
  chatbotOpen = false;
  chatbotInput = '';
  chatbotSending = false;
  chatbotError = '';
  chatbotMessages: ChatbotMessage[] = [];
  readonly chatbotQuickPrompts = [
    'Combien d’audits ont été enregistrés ?',
    'Quel est le taux de conformité de Gipa en 2026 ?',
    'Quelle est la meilleure filiale visible dans la base ?',
  ];
  readonly branchMapLocations: BranchMapLocation[] = [
    { sector: 'agro', branch: 'gipa', longitude: 10.4456, latitude: 36.6831 },
    { sector: 'agro', branch: 'agromed', longitude: 10.877781, latitude: 34.955198 },
    { sector: 'agro', branch: 'sokapo', longitude: 10.774356, latitude: 34.749975 },
    { sector: 'aliment', branch: 'nutrimix sfax', longitude: 10.774346, latitude: 34.749829 },
    { sector: 'aliment', branch: 'sna tunis', longitude: 10.38452, latitude: 36.69836 },
    { sector: 'aliment', branch: 'premix', longitude: 10.099698, latitude: 36.580761 },
    { sector: 'avicole', branch: 'couvoir cedria', longitude: 10.380901, latitude: 36.708391 },
    { sector: 'avicole', branch: 'couvoir ennajeh', longitude: 10.491539, latitude: 36.604089 },
  ];
  selectedBranchMapLocation: BranchMapLocation = this.branchMapLocations[0];
  checklistItems: ChecklistItem[] = [];
  checklistAxes: ChecklistAxe[] = [];
  checklistMonth: string = '';
  checklistYear: string = '';
  checklistLaboratoire: string = '';
  checklistAuditeur: string = '';
  adminAiMonth: string = '';
  adminAiYear: string = '';
  adminAiBranchId: number | null = null;
  readonly adminAiMonthOptions = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin', 'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre'];
  readonly adminAiYearOptions = Array.from({ length: 5 }, (_, index) => String(2026 + index));
  readonly adminPowerBiDashboardBaseUrl =
    'https://app.powerbi.com/reportEmbed?reportId=4a623193-4189-4b1f-aae9-23b7816582d0&autoAuth=true&ctid=dbd6664d-4eb9-46eb-99d8-5c43ba153c61&navContentPaneEnabled=false&filterPaneEnabled=false';
  adminPowerBiDashboardRefreshKey = Date.now();
  isChecklistMode = false;
  showIsoForm = false;
  private observer?: IntersectionObserver;
  private toastTimeout?: ReturnType<typeof setTimeout>;
  private readonly requestTimeoutMs = 20000;
  private readonly mlRequestTimeoutMs = 8000;
  private readonly scopeCacheKeyLite = 'app.scope.lite';
  private readonly scopeCacheKeyFull = 'app.scope.full';
  private readonly evaluationSummaryCacheKey = 'app.evaluations.summary';
  private readonly userEvaluationCacheKey = 'app.evaluations.user';
  private readonly chatbotCacheKey = 'app.chatbot.messages.v2';
  private readonly themeStorageKey = 'app.theme';
  private readonly adminNotificationSeenKeyPrefix = 'app.admin.notifications.lastSeen';
  private readonly adminUserNotificationSeenKeyPrefix = 'app.admin.userNotifications.lastSeen';
  private activeMlPredictionController?: AbortController;
  private readonly noCacheHeaders = new HttpHeaders({
    'Cache-Control': 'no-cache, no-store, must-revalidate',
    'Pragma': 'no-cache',
    'Expires': '0',
  });
  private httpOptions = { withCredentials: true, headers: this.noCacheHeaders };

  constructor(
    private http: HttpClient,
    private cdr: ChangeDetectorRef,
    private ngZone: NgZone,
    private sanitizer: DomSanitizer,
  ) {}

  get selectedBranchMapUrl(): SafeResourceUrl {
    const location = this.selectedBranchMapLocation;
    const query = `${location.latitude},${location.longitude}`;
    return this.sanitizer.bypassSecurityTrustResourceUrl(
      `https://maps.google.com/maps?q=${encodeURIComponent(query)}&z=9&output=embed`
    );
  }

  get adminPowerBiDashboardUrl(): SafeResourceUrl {
    return this.sanitizer.bypassSecurityTrustResourceUrl(
      `${this.adminPowerBiDashboardBaseUrl}&refresh=${this.adminPowerBiDashboardRefreshKey}`
    );
  }

  selectBranchMapLocation(location: BranchMapLocation) {
    this.selectedBranchMapLocation = location;
  }

  refreshAdminPowerBiDashboard() {
    this.adminPowerBiDashboardRefreshKey = Date.now();
  }

  get mlopsRegistryEntries(): Array<{ key: string; value: MlopsRegistryEntry }> {
    if (!this.mlopsStatus?.registry) {
      return [];
    }
    return Object.entries(this.mlopsStatus.registry).map(([key, value]) => ({ key, value }));
  }

  get mlopsRecentRunGroups(): Array<{ key: string; runs: MlopsRun[] }> {
    if (!this.mlopsStatus?.recent_runs) {
      return [];
    }
    return Object.entries(this.mlopsStatus.recent_runs).map(([key, runs]) => ({ key, runs }));
  }

  get mlopsArtifactEntries(): Array<{ key: string; value: MlopsArtifact }> {
    if (!this.mlopsStatus?.artifacts) {
      return [];
    }
    return Object.entries(this.mlopsStatus.artifacts).map(([key, value]) => ({ key, value }));
  }

  selectAiWorkspace(mode: 'predict' | 'improve') {
    this.aiWorkspaceMode = mode;
    this.mlPredictionError = '';
    if (mode === 'improve' && !this.mlopsStatus && !this.mlopsLoading) {
      this.loadMlopsStatus();
    }
  }

  loadMlopsStatus() {
    this.mlopsLoading = true;
    this.mlopsError = '';

    this.http.get<MlopsStatusResponse>('/api/auth/ml/status/', this.httpOptions).pipe(
      timeout(this.requestTimeoutMs),
      finalize(() => {
        this.mlopsLoading = false;
        this.cdr.detectChanges();
      }),
    ).subscribe({
      next: (data) => {
        this.mlopsStatus = data;
        this.mlopsError = '';
      },
      error: (e) => {
        this.mlopsError = e.error?.detail || "Impossible de charger les indicateurs d'amélioration.";
      },
    });
  }

  metricEntries(metrics?: Record<string, string | number | null>) {
    return Object.entries(metrics || {}).filter(([key]) => key !== 'modele');
  }

  formatMetricLabel(label: string) {
    const labels: Record<string, string> = {
      accuracy: 'Fiabilité globale',
      balanced_accuracy: 'Équilibre de détection',
      precision: 'Précision des alertes',
      recall: 'Couverture des risques',
      f1: 'Niveau global',
      roc_auc: 'Capacité à distinguer les risques',
      mae: 'Écart moyen sur la note',
      rmse: 'Écart global sur la note',
      r2: 'Qualité de prévision',
      modele: 'Méthode',
    };
    return labels[label] || label.replace(/_/g, ' ');
  }

  formatObjectiveLabel(value: string) {
    const labels: Record<string, string> = {
      objectif1_non_conformite: 'Objectif 1 - Anticiper les non-conformités',
      objectif2_prediction_note: 'Objectif 2 - Anticiper la note qualité',
    };
    return labels[value] || value.replace(/_/g, ' ');
  }

  formatTaskTypeLabel(value: string) {
    const labels: Record<string, string> = {
      classification: 'Alerte non-conformité',
      regression: 'Prévision de note',
    };
    return labels[value] || value;
  }

  formatRunStatusLabel(value: string) {
    const labels: Record<string, string> = {
      completed: 'Mise à jour terminée',
      running: 'Mise à jour en cours',
      failed: 'Mise à jour en échec',
    };
    return labels[value] || value;
  }

  formatArtifactLabel(value: string) {
    const labels: Record<string, string> = {
      'objectif1_non_conformite.joblib': 'Fichier de prévision des non-conformités',
      'objectif2_note.joblib': 'Fichier de prévision des notes',
    };
    return labels[value] || value;
  }

  formatMetricValue(value: string | number | boolean | null | undefined) {
    if (value === null || value === undefined || value === '') {
      return '—';
    }
    if (typeof value === 'number') {
      return Number.isInteger(value) ? String(value) : value.toFixed(4);
    }
    return String(value);
  }

  formatMlopsTimestamp(value?: string | null) {
    if (!value) {
      return '—';
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return value;
    }
    return date.toLocaleString('fr-FR');
  }

  formatFileSize(size?: number) {
    if (!size || size <= 0) {
      return '—';
    }
    const units = ['o', 'Ko', 'Mo', 'Go'];
    let current = size;
    let unitIndex = 0;
    while (current >= 1024 && unitIndex < units.length - 1) {
      current /= 1024;
      unitIndex += 1;
    }
    return `${current.toFixed(unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
  }

  private createEmptyEvaluationRow(): EvaluationRow {
    return {
      month: '',
      year: '',
      filiale: '',
      code: '',
      laboratoire: '',
      axe_evaluation: '',
      criteres: '',
      note: '',
      ponderation: '',
      observations: '',
      isNew: true,
      isSaving: false,
      isDeleting: false,
      editing: true,
    };
  }

  private getAbsoluteChecklistIndex(axisIndex: number, criterionIndex: number): number {
    let offset = 0;
    for (let index = 0; index < axisIndex; index += 1) {
      offset += ISO_17025_CHECKLIST[index]?.criteria.length || 0;
    }
    return offset + criterionIndex;
  }

  getChecklistPredictionRow(axisIndex: number, criterionIndex: number): MlPredictionRow | null {
    const absoluteIndex = this.getAbsoluteChecklistIndex(axisIndex, criterionIndex);
    return this.checklistPrediction?.rows.find((row) => row.row_index === absoluteIndex) || null;
  }

  getSelectedPredictionRow(rowIndex: number): MlPredictionRow | null {
    return this.selectedEvaluationPrediction?.rows.find((row) => row.row_index === rowIndex) || null;
  }

  private buildAdminAiPredictionPayload(): any[] {
    const selectedBranch = this.branches.find((branch) => branch.id === this.adminAiBranchId);
    if (!selectedBranch) {
      return [];
    }

    const payload: any[] = [];
    ISO_17025_CHECKLIST.forEach((axis) => {
      axis.criteria.forEach((criterion) => {
        payload.push({
          month: this.adminAiMonth || '',
          year: String(this.adminAiYear || ''),
          filiale: selectedBranch.name,
          code: String(selectedBranch.code),
          laboratoire: selectedBranch.laboratoireName || selectedBranch.name,
          auditeur: `${this.userFirstName} ${this.userLastName}`.trim(),
          axe_evaluation: axis.title,
          criteres: criterion.text,
          note: '',
          ponderation: String(criterion.weight),
          observations: '',
          secteur_name: selectedBranch.sector,
        });
      });
    });
    return payload;
  }

  private buildSelectedEvaluationPredictionPayload(): any[] {
    return this.selectedEvaluation.map((row) => ({
      month: row.month,
      year: row.year,
      filiale: row.filiale || row.filiale_name || '',
      code: row.code || row.filiale_code || '',
      laboratoire: row.laboratoire || row.laboratoire_name || '',
      user_name: row.user_name || '',
      axe_evaluation: row.axe_evaluation,
      criteres: row.criteres,
      note: row.note,
      ponderation: row.ponderation,
      observations: row.observations,
      secteur_name: row.secteur_name || '',
    }));
  }

  private async requestMlPrediction(target: 'checklist' | 'detail', evaluations: any[]) {
    if (!evaluations.length) {
      this.ngZone.run(() => {
        this.mlPredictionError = 'Aucune donnée disponible pour lancer la prédiction.';
        this.cdr.detectChanges();
      });
      return;
    }

    this.activeMlPredictionController?.abort();
    const controller = new AbortController();
    this.activeMlPredictionController = controller;
    const timeoutId = setTimeout(() => controller.abort(), this.mlRequestTimeoutMs);

    this.ngZone.run(() => {
      this.mlPredictionLoading = true;
      this.mlPredictionError = '';
      if (target === 'checklist') {
        this.checklistPrediction = null;
      } else {
        this.selectedEvaluationPrediction = null;
      }
      this.cdr.detectChanges();
    });

    try {
      const response = await fetch('/api/auth/ml/predict/', {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'Cache-Control': 'no-cache, no-store, must-revalidate',
          'Pragma': 'no-cache',
          'Expires': '0',
        },
        body: JSON.stringify({ evaluations }),
        signal: controller.signal,
      });

      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data?.detail || "Impossible de calculer la prédiction IA.");
      }

      if (controller !== this.activeMlPredictionController) {
        return;
      }

      const prediction = data as MlPredictionResponse;
      this.ngZone.run(() => {
        if (target === 'checklist') {
          this.checklistPrediction = prediction;
        } else {
          this.selectedEvaluationPrediction = prediction;
        }
        this.cdr.detectChanges();
      });
    } catch (e: any) {
      if (controller !== this.activeMlPredictionController) {
        return;
      }

      this.ngZone.run(() => {
        if (e?.name === 'AbortError') {
          this.mlPredictionError = "La prédiction prend trop de temps. Veuillez réessayer.";
        } else {
          this.mlPredictionError = e?.message || 'Impossible de calculer la prédiction IA.';
        }
        this.showToast(this.mlPredictionError, 'error');
        this.cdr.detectChanges();
      });
    } finally {
      clearTimeout(timeoutId);
      if (controller === this.activeMlPredictionController) {
        this.ngZone.run(() => {
          this.activeMlPredictionController = undefined;
          this.mlPredictionLoading = false;
          this.cdr.detectChanges();
        });
      }
    }
  }

  predictAdminAi() {
    const predictionYear = String(this.adminAiYear ?? '').trim();
    const predictionMonth = String(this.adminAiMonth ?? '').trim();

    if (!predictionYear) {
      this.mlPredictionError = "L'année de prédiction est obligatoire.";
      return;
    }
    if (!predictionMonth) {
      this.mlPredictionError = 'Le mois de prédiction est obligatoire.';
      return;
    }
    if (!this.adminAiBranchId) {
      this.mlPredictionError = 'La filiale est obligatoire.';
      return;
    }
    if (!this.branches.length) {
      this.mlPredictionError = 'Les filiales ne sont pas encore chargées. Veuillez réessayer.';
      return;
    }
    void this.requestMlPrediction('checklist', this.buildAdminAiPredictionPayload());
  }

  predictSelectedEvaluation() {
    void this.requestMlPrediction('detail', this.buildSelectedEvaluationPredictionPayload());
  }

  private compareEvaluationValues(left: string, right: string) {
    const a = String(left || '').trim().toLocaleLowerCase('fr');
    const b = String(right || '').trim().toLocaleLowerCase('fr');

    if (!a && !b) {
      return 0;
    }
    if (!a) {
      return 1;
    }
    if (!b) {
      return -1;
    }
    return a.localeCompare(b, 'fr', { sensitivity: 'base' });
  }

  initializeAdminAiWorkspace(reset = false) {
    const now = new Date();
    if (reset || !this.adminAiMonth) {
      this.adminAiMonth = this.adminAiMonthOptions[now.getMonth()] || 'Janvier';
    }
    if (reset || !this.adminAiYear) {
      this.adminAiYear = String(now.getFullYear());
    }
    if (reset || !this.adminAiBranchId) {
      this.adminAiBranchId = this.branches[0]?.id ?? null;
    }
    this.mlPredictionError = '';
    this.checklistPrediction = null;
    if (reset) {
      this.aiWorkspaceMode = 'predict';
    }
  }

  private sortEvaluations() {
    this.evaluations = [...this.evaluations].sort((left, right) =>
      this.compareEvaluationValues(left.axe_evaluation, right.axe_evaluation) ||
      this.compareEvaluationValues(left.criteres, right.criteres) ||
      this.compareEvaluationValues(left.filiale, right.filiale) ||
      this.compareEvaluationValues(left.laboratoire, right.laboratoire) ||
      this.compareEvaluationValues(left.code, right.code) ||
      this.compareEvaluationValues(left.month, right.month) ||
      this.compareEvaluationValues(left.year, right.year) ||
      (left.line_pk || 0) - (right.line_pk || 0)
    );
  }

  get evaluationAxisGroups(): EvaluationAxisGroup[] {
    const groups = new Map<string, EvaluationAxisGroup>();

    for (const evaluation of this.evaluations) {
      const axis = String(evaluation.axe_evaluation || '').trim() || 'Sans axe d’évaluation';
      const existingGroup = groups.get(axis);

      if (existingGroup) {
        existingGroup.rows.push(evaluation);
        existingGroup.total += 1;
        if (evaluation.line_pk) {
          existingGroup.existingCount += 1;
        } else {
          existingGroup.newCount += 1;
        }
        continue;
      }

      groups.set(axis, {
        axis,
        rows: [evaluation],
        total: 1,
        existingCount: evaluation.line_pk ? 1 : 0,
        newCount: evaluation.line_pk ? 0 : 1,
      });
    }

    return Array.from(groups.values());
  }

  getEvaluationIndex(evaluation: EvaluationRow) {
    return this.evaluations.indexOf(evaluation);
  }

  /**
   * Formate l'affichage d'une période (Mois + Trimestre + Année) en chaîne compacte.
   */
  formatPeriode(evaluation: EvaluationRow): string {
    const mois = (evaluation.month || evaluation.trimestre || '').toString().trim();
    const annee = (evaluation.year || '').toString().trim();
    const trimestre = (evaluation.trimestre || '').toString().trim();

    if (!mois && !annee) {
      return '—';
    }
    if (trimestre && !mois) {
      return `${trimestre} ${annee}`.trim();
    }
    if (mois && annee) {
      return `${mois} ${annee}`;
    }
    return mois || annee;
  }

  ngOnInit() {
    window.addEventListener('iso-form-save', this.handleIsoFormSave);
    this.initializeTheme();
    this.hydrateSessionState();
    this.initializeChatbot();
  }

  ngAfterViewInit() {
    this.initScrollReveal();
  }

  ngOnDestroy() {
    window.removeEventListener('iso-form-save', this.handleIsoFormSave);
    this.observer?.disconnect();
  }

  private handleIsoFormSave = (event?: Event) => {
    const customEvent = event as CustomEvent;
    if (customEvent && customEvent.detail && customEvent.detail.evaluations) {
      this.saveIsoForm(customEvent.detail.evaluations);
    }
  };

  private readSessionCache<T>(key: string): T | null {
    if (typeof window === 'undefined') {
      return null;
    }

    try {
      const raw = sessionStorage.getItem(key);
      return raw ? JSON.parse(raw) as T : null;
    } catch {
      return null;
    }
  }

  private writeSessionCache(key: string, value: unknown) {
    if (typeof window === 'undefined') {
      return;
    }

    try {
      sessionStorage.setItem(key, JSON.stringify(value));
    } catch {
      // Ignore storage quota and serialization errors.
    }
  }

  private clearSessionDataCache() {
    if (typeof window === 'undefined') {
      return;
    }

    try {
      [
        'evaluationFilters',
        this.scopeCacheKeyLite,
        this.scopeCacheKeyFull,
        this.evaluationSummaryCacheKey,
        this.userEvaluationCacheKey,
      ].forEach((key) => sessionStorage.removeItem(key));
    } catch {
      // Ignore browser cache cleanup errors and keep the app usable.
    }
  }

  private hydrateSessionState() {
    const cachedScope = this.readSessionCache<ScopeResponse>(this.scopeCacheKeyFull);
    if (!cachedScope?.role || !cachedScope?.me?.id) {
      return;
    }

    this.connected = true;
    this.applyScopeResponse(cachedScope, false);
    this.syncConnectedUi('hydrate-cache');
    const cachedEvaluationSummaries = this.readSessionCache<UserEvaluationSummary[]>(this.evaluationSummaryCacheKey);
    if (cachedEvaluationSummaries?.length) {
      this.applyEvaluationSummaries(cachedEvaluationSummaries);
    }
    const cachedUserEvaluations = this.readSessionCache<UserEvaluationSummary[]>(this.userEvaluationCacheKey);
    if (cachedUserEvaluations?.length) {
      this.applyUserEvaluationList(cachedUserEvaluations);
    }

    setTimeout(() => this.loadScope(true, true), 0);
  }

  private initializeChatbot() {
    const cachedMessages = this.readSessionCache<ChatbotMessage[]>(this.chatbotCacheKey);
    if (cachedMessages?.length) {
      this.chatbotMessages = cachedMessages;
      return;
    }

    this.chatbotMessages = [
      {
        role: 'assistant',
        text: 'Bonjour, je suis votre assistant qualité. Je peux vous aider sur les évaluations, la conformité, les axes, les observations, les rôles et l’utilisation de cette application.',
        createdAt: new Date().toISOString(),
      },
    ];
    this.persistChatbotMessages();
  }

  private persistChatbotMessages() {
    this.writeSessionCache(this.chatbotCacheKey, this.chatbotMessages.slice(-20));
  }

  toggleChatbot(forceState?: boolean) {
    this.chatbotOpen = typeof forceState === 'boolean' ? forceState : !this.chatbotOpen;
    if (this.chatbotOpen) {
      this.chatbotError = '';
      this.scrollChatbotToBottom();
    }
  }

  useChatbotPrompt(prompt: string) {
    this.chatbotInput = prompt;
    this.toggleChatbot(true);
  }

  sendChatbotMessage() {
    const message = this.chatbotInput.trim();
    if (!message || this.chatbotSending) {
      return;
    }
    const userMessage: ChatbotMessage = {
      role: 'user',
      text: message,
      createdAt: new Date().toISOString(),
    };

    this.chatbotMessages = [...this.chatbotMessages, userMessage];
    this.persistChatbotMessages();
    this.chatbotInput = '';
    this.chatbotSending = true;
    this.chatbotError = '';
    this.scrollChatbotToBottom();
    const assistantIndex = this.chatbotMessages.length;
    this.chatbotMessages = [
      ...this.chatbotMessages,
      {
        role: 'assistant',
        text: '',
        createdAt: new Date().toISOString(),
      },
    ];
    this.persistChatbotMessages();
    this.cdr.detectChanges();

    const requestBody = {
      message,
      history: this.chatbotMessages
        .slice(0, assistantIndex)
        .slice(-1)
        .map((item) => ({
          role: item.role,
          text: item.text.slice(0, 160),
        })),
      role: this.userRole || this.role,
      sector: this.userSectorName || '',
      stream: true,
    };

    const applyAssistantChunk = (delta: string) => {
      const currentMessage = this.chatbotMessages[assistantIndex];
      const nextText = `${currentMessage?.text || ''}${delta}`;
      this.ngZone.run(() => {
        this.chatbotMessages = this.chatbotMessages.map((item, index) =>
          index === assistantIndex ? { ...item, text: nextText } : item
        );
        this.persistChatbotMessages();
        this.cdr.detectChanges();
        this.scrollChatbotToBottom();
      });
    };

    const finalizeStream = () => {
      this.ngZone.run(() => {
        this.chatbotSending = false;
        this.persistChatbotMessages();
        this.cdr.detectChanges();
        this.scrollChatbotToBottom();
      });
    };

    const failStream = (errorMessage: string) => {
      this.ngZone.run(() => {
        this.chatbotError = errorMessage;
        this.chatbotMessages = this.chatbotMessages.map((item, index) =>
          index === assistantIndex
            ? { ...item, text: item.text || errorMessage }
            : item
        );
        this.persistChatbotMessages();
        this.chatbotSending = false;
        this.cdr.detectChanges();
        this.scrollChatbotToBottom();
      });
      this.showToast(errorMessage, 'error');
    };

    void (async () => {
      try {
        const response = await fetch('/api/auth/chatbot/', {
          method: 'POST',
          credentials: 'include',
          headers: {
            'Content-Type': 'application/json',
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0',
          },
          body: JSON.stringify(requestBody),
        });

        if (!response.ok || !response.body) {
          throw new Error('Le chatbot est momentanément indisponible.');
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        while (true) {
          const { done, value } = await reader.read();
          if (done) {
            break;
          }

          buffer += decoder.decode(value, { stream: true });
          const events = buffer.split('\n\n');
          buffer = events.pop() || '';

          for (const event of events) {
            const lines = event.split('\n');
            for (const rawLine of lines) {
              const line = rawLine.trim();
              if (!line.startsWith('data:')) {
                continue;
              }

              const payloadText = line.slice(5).trim();
              if (!payloadText) {
                continue;
              }

              const payload = JSON.parse(payloadText) as { delta?: string; done?: boolean; error?: string };
              if (payload.error) {
                throw new Error(payload.error);
              }

              if (payload.delta) {
                applyAssistantChunk(payload.delta);
              }

              if (payload.done) {
                finalizeStream();
                return;
              }
            }
          }
        }

        finalizeStream();
      } catch (error) {
        const errorMessage = error instanceof Error && error.message
          ? error.message
          : 'Le chatbot est momentanément indisponible.';
        failStream(errorMessage);
      }
    })();
  }

  private initializeTheme() {
    if (typeof window === 'undefined') {
      return;
    }

    let savedTheme = '';
    try {
      savedTheme = localStorage.getItem(this.themeStorageKey) || '';
    } catch {
      savedTheme = '';
    }

    if (savedTheme === 'dark' || savedTheme === 'light') {
      this.applyTheme(savedTheme);
      return;
    }

    const prefersDark = typeof window.matchMedia === 'function'
      ? window.matchMedia('(prefers-color-scheme: dark)').matches
      : false;
    this.applyTheme(prefersDark ? 'dark' : 'light');
  }

  toggleTheme() {
    this.applyTheme(this.isDarkMode ? 'light' : 'dark');
  }

  private applyTheme(theme: 'light' | 'dark') {
    this.isDarkMode = theme === 'dark';

    if (typeof document !== 'undefined') {
      document.documentElement.setAttribute('data-theme', theme);
      document.body.setAttribute('data-theme', theme);
    }

    if (typeof window !== 'undefined') {
      try {
        localStorage.setItem(this.themeStorageKey, theme);
      } catch {
        // Ignore storage failures and keep the in-memory theme.
      }
    }
  }

  onChatbotInputKeydown(event: KeyboardEvent) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.sendChatbotMessage();
    }
  }

  clearChatbotConversation() {
    this.chatbotMessages = [
      {
        role: 'assistant',
        text: 'Conversation réinitialisée. Je suis prêt à vous aider à nouveau.',
        createdAt: new Date().toISOString(),
      },
    ];
    this.chatbotError = '';
    this.persistChatbotMessages();
    this.scrollChatbotToBottom();
  }

  private scrollChatbotToBottom() {
    if (typeof document === 'undefined') {
      return;
    }

    setTimeout(() => {
      const panel = document.querySelector<HTMLElement>('.chatbot-messages');
      if (panel) {
        panel.scrollTop = panel.scrollHeight;
      }
    }, 0);
  }

  private applyEvaluationSummaries(evaluations: UserEvaluationSummary[]) {
    this.evaluationSummaries = evaluations;
    this.evaluationSummariesLoaded = true;
    this.evaluationSummariesStale = false;
    this.evaluationOverview.session_count = evaluations.length;
    this.evaluationOverviewLoaded = true;
    this.evaluationOverviewStale = false;
    this.evaluationPage = 1;
    this.updateAdminNotificationCount(evaluations);
    this.extractEvaluationFilters(evaluations);
    this.evaluationSuccess = evaluations.length
      ? `${evaluations.length} évaluation(s) récapitulatives chargée(s).`
      : 'Aucune évaluation enregistrée trouvée.';
  }

  private applyUserEvaluationList(evaluations: UserEvaluationSummary[]) {
    this.userEvaluationList = evaluations;
    this.userEvaluationListLoaded = true;
    this.userEvaluationListStale = false;
  }

  private mapEvaluationSummary(evaluation: any): UserEvaluationSummary {
    const evaluationId = Number(evaluation.id || 0);
    return {
      id: evaluationId,
      line_pk: evaluation.line_pk || null,
      periode: evaluation.periode || `${evaluation.mois || ''} ${evaluation.annee || ''}`.trim() || '—',
      filiale_name: evaluation.filiale_name || evaluation.filiale || '—',
      secteur_name: evaluation.secteur_name || '—',
      manager_name: evaluation.manager_name || '—',
      user_name: evaluation.user_name || '—',
      note_moyenne: evaluation.note_moyenne ?? evaluation.moyenne ?? '—',
      min_note: evaluation.min_note ?? null,
      max_note: evaluation.max_note ?? null,
      conformite_globale: evaluation.conformite_globale ?? evaluation.tx_conformite ?? '—',
      mois: evaluation.mois || '',
      annee: evaluation.annee || '',
      date_id: evaluation.date_id || null,
      filiale_id: evaluation.filiale_id || null,
      sector_id: evaluation.sector_id || null,
      manager_id: evaluation.manager_id || null,
      laboratoire_id: evaluation.laboratoire_id || null,
      laboratoire_name: evaluation.laboratoire_name || '—',
      user_id: evaluation.user_id || null,
      created_at: evaluation.created_at || null,
    };
  }

  private getAdminNotificationSeenKey() {
    return `${this.adminNotificationSeenKeyPrefix}.${this.currentUserId || 'anonymous'}`;
  }

  private getAdminNotificationLastSeenTimestamp() {
    if (typeof window === 'undefined') {
      return 0;
    }

    try {
      return Number(localStorage.getItem(this.getAdminNotificationSeenKey()) || '0');
    } catch {
      return 0;
    }
  }

  private getAdminUserNotificationSeenKey() {
    return `${this.adminUserNotificationSeenKeyPrefix}.${this.currentUserId || 'anonymous'}`;
  }

  private getEvaluationCreatedAtTimestamp(evaluation: UserEvaluationSummary) {
    const createdAt = evaluation.created_at ? Date.parse(evaluation.created_at) : NaN;
    return Number.isFinite(createdAt) ? createdAt : 0;
  }

  private getLatestEvaluationTimestamp(evaluations: UserEvaluationSummary[]) {
    return evaluations.reduce((latest, evaluation) =>
      Math.max(latest, this.getEvaluationCreatedAtTimestamp(evaluation)), 0
    );
  }

  private getUserCreatedAtTimestamp(user: AdminUser) {
    const createdAt = user.date_joined ? Date.parse(user.date_joined) : NaN;
    return Number.isFinite(createdAt) ? createdAt : 0;
  }

  private getLatestUserTimestamp(users: AdminUser[]) {
    return users.reduce((latest, user) => Math.max(latest, this.getUserCreatedAtTimestamp(user)), 0);
  }

  private updateAdminNotificationCount(evaluations: UserEvaluationSummary[]) {
    if (this.userRole !== 'general_manager' || typeof window === 'undefined') {
      this.adminNotificationCount = 0;
      return;
    }

    let lastSeen = 0;
    try {
      lastSeen = Number(localStorage.getItem(this.getAdminNotificationSeenKey()) || '0');
    } catch {
      lastSeen = 0;
    }

    this.adminNotificationCount = evaluations.filter((evaluation) =>
      this.getEvaluationCreatedAtTimestamp(evaluation) > lastSeen
    ).length;
  }

  private updateAdminUserNotificationCount(users: AdminUser[], sectorManagers: AdminUser[]) {
    if (this.userRole !== 'general_manager' || typeof window === 'undefined') {
      this.adminUserNotificationCount = 0;
      return;
    }

    let lastSeen = 0;
    try {
      lastSeen = Number(localStorage.getItem(this.getAdminUserNotificationSeenKey()) || '0');
    } catch {
      lastSeen = 0;
    }

    const allUsers = [...users, ...sectorManagers];
    this.adminUserNotificationCount = allUsers.filter((user) =>
      this.getUserCreatedAtTimestamp(user) > lastSeen
    ).length;
  }

  private markAdminNotificationsAsSeen() {
    if (this.userRole !== 'general_manager' || typeof window === 'undefined') {
      return;
    }

    const latestTimestamp = this.getLatestEvaluationTimestamp(this.evaluationSummaries);
    try {
      localStorage.setItem(this.getAdminNotificationSeenKey(), String(latestTimestamp));
    } catch {
      // Ignore storage failures and only reset the badge in memory.
    }
    this.adminNotificationCount = 0;
  }

  private markAdminUserNotificationsAsSeen() {
    if (this.userRole !== 'general_manager' || typeof window === 'undefined') {
      return;
    }

    const latestTimestamp = Math.max(
      this.getLatestUserTimestamp(this.users),
      this.getLatestUserTimestamp(this.sectorManagers),
    );
    try {
      localStorage.setItem(this.getAdminUserNotificationSeenKey(), String(latestTimestamp));
    } catch {
      // Ignore storage failures and only reset the badge in memory.
    }
    this.adminUserNotificationCount = 0;
  }

  private refreshAdminNotifications() {
    if (this.userRole !== 'general_manager') {
      this.adminNotificationCount = 0;
      return;
    }
    if (this.adminNotificationRefreshLoading) {
      return;
    }

    this.adminNotificationRefreshLoading = true;
    this.http.get<{ evaluations: any[] }>(this.withNoCache('/api/auth/evaluations-summary/'), this.httpOptions)
      .pipe(
        timeout(this.requestTimeoutMs),
        finalize(() => {
          this.adminNotificationRefreshLoading = false;
        })
      )
      .subscribe({
        next: (response) => {
          const evaluations = (response.evaluations || []).map((evaluation) => this.mapEvaluationSummary(evaluation));
          this.evaluationSummaries = evaluations;
          this.evaluationSummariesLoaded = true;
          this.evaluationSummariesStale = false;
          this.updateAdminNotificationCount(evaluations);
          this.writeSessionCache(this.evaluationSummaryCacheKey, evaluations);
        },
        error: () => {
          // Keep the current badge state when the silent refresh fails.
        },
      });
  }

  private loadEvaluationOverview(force = false) {
    if (!force && this.evaluationOverviewLoading) {
      return;
    }
    if (!force && this.evaluationOverviewLoaded && !this.evaluationOverviewStale) {
      return;
    }

    const endpoint = this.userRole === 'user'
      ? '/api/auth/user/evaluations-overview/'
      : '/api/auth/evaluations-overview/';
    const params = new URLSearchParams();

    if (this.userRole === 'general_manager') {
      const since = this.getAdminNotificationLastSeenTimestamp();
      if (since > 0) {
        params.set('since', String(since));
      }
    }

    const url = params.toString()
      ? `${endpoint}?${params.toString()}`
      : endpoint;

    this.evaluationOverviewLoading = true;
    this.http.get<{
      session_count?: number;
      row_count?: number;
      latest_created_at?: string | null;
      new_session_count?: number;
    }>(this.withNoCache(url), this.httpOptions)
      .pipe(
        timeout(this.requestTimeoutMs),
        finalize(() => {
          this.evaluationOverviewLoading = false;
        })
      )
      .subscribe({
        next: (response) => {
          this.evaluationOverview = {
            session_count: Number(response.session_count || 0),
            row_count: Number(response.row_count || 0),
            latest_created_at: response.latest_created_at || null,
            new_session_count: Number(response.new_session_count || 0),
          };
          this.evaluationOverviewLoaded = true;
          this.evaluationOverviewStale = false;
          if (this.userRole === 'general_manager') {
            this.adminNotificationCount = this.evaluationOverview.new_session_count;
          }
        },
        error: () => {
          if (this.userRole === 'general_manager') {
            this.adminNotificationCount = 0;
          }
        },
      });
  }

  private applyScopeResponse(r: ScopeResponse, lite: boolean) {
    this.userRole = r.role;
    this.currentUserId = r.me?.id || null;
    this.userFirstName = r.me?.first_name || '';
    this.userLastName = r.me?.last_name || '';
    this.userEmail = r.me?.email || '';
    this.userBranchName = r.me?.branch__name || '';
    this.userBranchCode = r.me?.branch_code || null;
    this.userSectorName = r.me?.managed_sector__name || r.me?.branch__sector__name || '';
    this.userAvatar = r.me?.avatar || '';

    if (lite) {
      if (this.userRole === 'user') {
        this.scopeDataLoaded = true;
        this.syncConnectedUi('scope-lite-user');
      } else if (!this.scopeDataLoaded) {
        setTimeout(() => this.loadScope(false, true), 0);
      }
      return;
    }

    if (this.userRole === 'general_manager' && (!this.evaluationOverviewLoaded || this.evaluationOverviewStale)) {
      this.loadEvaluationOverview();
    } else if (this.userRole !== 'general_manager') {
      this.adminNotificationCount = 0;
      this.adminUserNotificationCount = 0;
    }

    this.users = (r.users || []).map((user) => ({
      ...user,
      branch__name: (user as any).branch__name || null,
      branch__sector__name: (user as any).branch__sector__name || null,
      date_joined: (user as any).date_joined || null,
    }));
    this.sectorManagers = (r.sectorManagers || []).map((user) => ({
      ...user,
      branch__name: (user as any).branch__name || null,
      managed_sector__name: (user as any).managed_sector__name || null,
      date_joined: (user as any).date_joined || null,
    }));
    this.updateAdminUserNotificationCount(this.users, this.sectorManagers);
    this.sectors = r.sectors.map((sector) => ({
      id: sector.id,
      name: sector.name,
      managerId: sector.manager_id || null,
      managerName: sector.manager__first_name || sector.manager__last_name ? [sector.manager__first_name, sector.manager__last_name].filter(Boolean).join(' ') : '',
    }));
    if (this.userRole === 'sector_manager') {
      this.userSectorName = this.sectors[0]?.name || this.userSectorName;
      this.sectorUsers = (r.users || []).map((user) => ({
        id: user.id,
        email: user.email,
        first_name: user.first_name,
        last_name: user.last_name,
        branch__name: (user as any).branch__name || null,
        branch__sector__name: (user as any).branch__sector__name || null,
      }));
    }
    this.branches = r.branches.map((branch) => ({
      id: branch.id,
      code: branch.code,
      name: branch.name,
      sector: branch['sector__name'] || '',
      sectorId: branch.sector_id,
      laboratoireId: branch.laboratoire_id || null,
      laboratoireName: branch['laboratoire__name'] || '',
    }));
    if (this.adminSection === 'ai' && !this.adminAiBranchId && this.branches.length > 0) {
      this.adminAiBranchId = this.branches[0].id;
    }

    if (this.userRole === 'user') {
      const me = (r.users || []).find((item: any) => item.id === this.currentUserId);
      if (me) {
        this.userFirstName = me.first_name || '';
        this.userLastName = me.last_name || '';
        this.userBranchName = me.branch__name || '';
        this.userSectorName = me.branch__sector__name || '';
      }
    }

    this.scopeDataLoaded = true;
    this.syncConnectedUi('scope-full');
  }

  private syncConnectedUi(source: string, scrollToTop = false) {
    const commitSync = () => {
      this.ngZone.run(() => {
        this.cdr.detectChanges();
        if (scrollToTop) {
          this.scrollToTop('auto');
        }
        this.initScrollReveal();
      });
    };

    if (typeof window === 'undefined') {
      return;
    }

    if (typeof requestAnimationFrame === 'function') {
      requestAnimationFrame(() => commitSync());
      return;
    }

    setTimeout(() => commitSync(), 0);
  }

  submit() {
    if (this.isAuthSubmitting) {
      return;
    }

    const body: any = {
      email: this.email,
      password: this.password,
      role: this.role,
    };

    if (this.mode === 'register') {
      body.first_name = this.firstName;
      body.last_name = this.lastName;
    }

    this.isAuthSubmitting = true;
    this.error = '';
    this.http.post<{ email: string, first_name?: string, last_name?: string, role?: string }>(`/api/auth/${this.mode}/`, body, this.httpOptions)
      .pipe(
        timeout(this.requestTimeoutMs),
        finalize(() => {
          this.isAuthSubmitting = false;
        })
      )
      .subscribe({
      next: r => {
        this.clearSessionDataCache();
        this.evaluationSummaries = [];
        this.userEvaluationList = [];
        this.evaluations = [];
        this.evaluationSummariesLoaded = false;
        this.evaluationSummariesStale = true;
        this.userEvaluationListLoaded = false;
        this.userEvaluationListStale = true;
        this.scopeDataLoaded = false;
        this.scopeDataLoading = false;
        this.selectedEvaluation = [];
        this.selectedEvaluationTitle = '';
        this.isEvaluationDetailMode = false;
        this.isEvaluationFormMode = false;
        this.resetEvaluationFilters();
        this.email = r.email;
        this.userFirstName = r.first_name || this.firstName;
        this.userLastName = r.last_name || this.lastName;
        this.userRole = r.role || this.role;
        this.connected = true;
        this.error = '';
        this.message = this.mode === 'login'
          ? 'Connexion réussie.'
          : 'Compte créé avec succès.';
        this.showToast(this.message, 'success');
        this.syncConnectedUi('login-success', true);
        setTimeout(() => this.loadScope(true, true), 0);
      },
      error: e => {
        this.error = this.getRequestErrorMessage(e, 'Erreur de connexion.');
        this.showToast(this.error, 'error');
      },
    });
  }

  logout() {
    this.http.post('/api/auth/logout/', {}, this.httpOptions).subscribe({
      error: () => {
        // Ignore backend logout errors and still return to the public home.
      },
    });

    this.connected = false;
    this.mode = 'login';
    this.showPassword = false;
    this.password = '';
    this.firstName = '';
    this.lastName = '';
    this.userFirstName = '';
    this.userLastName = '';
    this.userEmail = '';
    this.userBranchName = '';
    this.userBranchCode = null;
    this.userSectorName = '';
    this.userAvatar = '';
    this.userRole = '';
    this.adminSection = 'home';
    this.userSection = 'home';
    this.selectedEvaluation = [];
    this.selectedEvaluationTitle = '';
    this.isEvaluationDetailMode = false;
    this.isEvaluationFormMode = false;
    this.message = 'Vous avez été déconnecté.';
    this.error = '';
    this.resetEvaluationFilters();
    this.evaluationSummariesLoaded = false;
    this.evaluationSummariesStale = true;
    this.evaluationOverviewLoaded = false;
    this.evaluationOverviewStale = true;
    this.evaluationOverview = {
      session_count: 0,
      row_count: 0,
      latest_created_at: null,
      new_session_count: 0,
    };
    this.userEvaluationListLoaded = false;
    this.userEvaluationListStale = true;
    this.laboratoriesLoaded = false;
    this.scopeDataLoaded = false;
    this.scopeDataLoading = false;
    this.showToast(this.message, 'info');
    void this.clearBrowserCaches();
    this.scrollToTop();
    setTimeout(() => this.initScrollReveal(), 0);
  }

  getRoleLabel(role: string) {
    const option = this.roleOptions.find((item) => item.value === role);
    return option ? option.label : role;
  }

  loadScope(lite = false, silent = false) {
    if (!lite && this.scopeDataLoading) {
      return;
    }

    if (!silent) {
      this.isLoadingScope = true;
    }
    if (!lite) {
      this.scopeDataLoading = true;
      const cachedScope = this.readSessionCache<ScopeResponse>(this.scopeCacheKeyFull);
      if (cachedScope?.me?.id && !this.scopeDataLoaded) {
        this.connected = true;
        this.applyScopeResponse(cachedScope, false);
      }
    }
    this.error = '';
    if (!lite) {
      this.resetEvaluationFilters();
    }
    const scopeUrl = lite ? '/api/auth/scope/?lite=1' : '/api/auth/scope/';
    this.http.get<ScopeResponse>(this.withNoCache(scopeUrl), this.httpOptions)
      .pipe(
        timeout(this.requestTimeoutMs),
        finalize(() => {
          this.isLoadingScope = false;
          if (!lite) {
            this.scopeDataLoading = false;
          }
        })
      )
      .subscribe({
      next: (r: ScopeResponse) => {
        this.connected = true;
        this.applyScopeResponse(r, lite);
        this.writeSessionCache(lite ? this.scopeCacheKeyLite : this.scopeCacheKeyFull, r);
      },
      error: (e) => {
        if (e?.status === 401) {
          this.connected = false;
          this.userRole = '';
          this.scopeDataLoaded = false;
          this.scopeDataLoading = false;
          this.clearSessionDataCache();
          if (!silent) {
            this.showToast('Session expirée. Veuillez vous reconnecter.', 'info');
          }
          return;
        }
        this.error = this.getRequestErrorMessage(e, 'Impossible de charger les donnees.');
        this.showToast(this.error, 'error');
      },
    });
  }

  private getBranchSectorId() {
    return this.branchForm.sectorId;
  }

  private markEvaluationListsStale() {
    this.evaluationSummariesStale = true;
    this.evaluationOverviewStale = true;
    this.userEvaluationListStale = true;
    this.writeSessionCache(this.evaluationSummaryCacheKey, []);
    this.writeSessionCache(this.userEvaluationCacheKey, []);
  }

  private withNoCache(url: string): string {
    const separator = url.includes('?') ? '&' : '?';
    return `${url}${separator}_ts=${Date.now()}`;
  }

  private getRequestErrorMessage(error: any, fallback: string): string {
    if (error?.name === 'TimeoutError') {
      return 'Le serveur met trop de temps a repondre. Veuillez reessayer.';
    }

    return error?.error?.errors?.join(' ') || error?.error?.detail || fallback;
  }

  private async clearBrowserCaches() {
    this.clearSessionDataCache();
  }

  private showToast(message: string, type: 'success' | 'error' | 'info' = 'success') {
    if (!message.trim()) {
      return;
    }

    this.toastMessage = message;
    this.toastType = type;

    if (this.toastTimeout) {
      clearTimeout(this.toastTimeout);
    }

    this.toastTimeout = setTimeout(() => {
      this.toastMessage = '';
    }, 3200);
  }

  private resetEvaluationFilters() {
    this.evaluationSearch = '';
    this.evaluationDateFilter = '';
    this.evaluationSectorFilter = null;
    this.evaluationManagerFilter = null;
    this.evaluationFilialeFilter = null;
    this.evaluationLaboratoireFilter = '';
    this.evaluationUserFilter = null;
  }

  onEvaluationFileChange(event: Event) {
    const input = event.target as HTMLInputElement;
    if (!input.files?.length) {
      return;
    }

    const file = input.files[0];
    const reader = new FileReader();

    reader.onload = (e) => {
      try {
        const data = e.target?.result;
        const workbook = XLSX.read(data, { type: 'array' });
        const firstSheet = workbook.SheetNames[0];
        const worksheet = workbook.Sheets[firstSheet];

        const normalizeHeader = (value: string) =>
          String(value || '')
            .trim()
            .toLowerCase()
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '')
            .replace(/[^a-z0-9 ]+/g, ' ')
            .replace(/\s+/g, ' ')
            .trim();

        const rows: any[][] = XLSX.utils.sheet_to_json(worksheet, { header: 1, defval: '' });

        if (!rows || rows.length === 0) {
          this.evaluationError = 'Fichier Excel vide ou en-têtes non détectés.';
          this.evaluations = [];
          this.evaluationFileName = '';
          return;
        }

        const headerRowIndex = rows.findIndex((row) =>
          row.some((cell: any) => {
            const normalized = normalizeHeader(String(cell || ''));
            return [
              'mois',
              'annee',
              'filiale',
              'code',
              'laboratoire',
              'axe d evaluation',
              'criteres d evaluation iso 17025',
              'criteres d evaluation',
              'note 20',
              'note',
              'ponderation',
              'observations',
            ].includes(normalized);
          })
        );

        if (headerRowIndex === -1) {
          const knownHeaders = rows[0]?.map((header: any) => normalizeHeader(String(header || ''))).join(', ');
          this.evaluationError = `En-têtes Excel non reconnues : ${knownHeaders}`;
          this.evaluations = [];
          this.evaluationFileName = '';
          return;
        }

        const headers = rows[headerRowIndex].map((header: any) => normalizeHeader(String(header || '')));
        const headerIndex = new Map<string, number>();
        headers.forEach((header: string, index: number) => {
          if (header) {
            headerIndex.set(header, index);
          }
        });

        const getValue = (row: any[], candidates: string[]) => {
          for (const candidate of candidates) {
            const normalized = normalizeHeader(candidate);
            if (headerIndex.has(normalized)) {
              return row[headerIndex.get(normalized)!] ?? '';
            }
          }
          return '';
        };

        this.evaluations = rows
          .slice(headerRowIndex + 1)
          .filter((row) => row.some((cell: any) => String(cell || '').trim() !== ''))
          .map((row) => ({
            month: String(getValue(row, ['Mois', 'Month'])).trim(),
            year: String(getValue(row, ['Année', 'Annee', 'Year'])).trim(),
            filiale: String(getValue(row, ['Filiale', 'Branch'])).trim(),
            code: String(getValue(row, ['Code'])).trim(),
            laboratoire: String(getValue(row, ['Laboratoire', 'Laboratory'])).trim(),
            axe_evaluation: String(
              getValue(row, [
                'Axe d’évaluation',
                "Axe d'evaluation",
                'Axe d evaluation',
                'Axe Evaluation',
              ])
            ).trim(),
            criteres: String(
              getValue(row, [
                'Critères d’évaluation ( ISO 17025)',
                'Critères d’évaluation',
                'Critères',
                'Criteria',
                'criteres d evaluation iso 17025',
              ])
            ).trim(),
            note: String(getValue(row, ['Note/20', 'Note', 'Note 20'])).trim(),
            ponderation: String(getValue(row, ['Pondération', 'Ponderation', 'Weight'])).trim(),
            observations: String(getValue(row, ['Observations', 'Observation'])).trim(),
            isNew: true,
          }))
          .filter((evaluation) =>
            Object.values(evaluation).some((value) => String(value).trim() !== '')
          );

        this.sortEvaluations();

        if (!this.evaluations.length) {
          const knownHeaders = rows[0]?.map((header: any) => normalizeHeader(String(header || ''))).join(', ');
          this.evaluationError = `Aucune ligne valide trouvée dans le fichier Excel. En-têtes détectées: ${knownHeaders}`;
          this.evaluationSuccess = '';
          this.evaluationFileName = '';
          return;
        }

        this.evaluationFileName = file.name;
        this.evaluationError = '';
        this.evaluationSuccess = `${this.evaluations.length} ligne(s) importée(s) avec succès.`;
      } catch (error) {
        this.evaluationError = 'Impossible de lire le fichier Excel.';
        this.evaluationSuccess = '';
        this.evaluations = [];
        this.evaluationFileName = '';
      }
    };

    reader.onerror = () => {
      this.evaluationError = 'Erreur lors de la lecture du fichier.';
      this.evaluations = [];
      this.evaluationFileName = '';
    };

    reader.readAsArrayBuffer(file);
  }

  addEvaluationRow() {
    this.evaluationError = '';
    this.evaluationSuccess = '';
    this.evaluationSaveMessage = '';
    this.evaluationSaveError = '';
    const row = this.createEmptyEvaluationRow();
    row.editing = true;
    this.evaluations = [...this.evaluations, row];
    this.sortEvaluations();
  }

  editEvaluationRow(evaluation: EvaluationRow) {
    evaluation.editing = true;
  }

  cancelEditEvaluation(evaluation: EvaluationRow) {
    evaluation.editing = false;
    if (!evaluation.line_pk) {
      const index = this.evaluations.indexOf(evaluation);
      if (index > -1) {
        this.evaluations.splice(index, 1);
        this.sortEvaluations();
      }
      if (this.userRole === 'user' && this.isEvaluationDetailMode) {
        const selIndex = this.selectedEvaluation.indexOf(evaluation);
        if (selIndex > -1) {
          this.selectedEvaluation.splice(selIndex, 1);
        }
        if (this.selectedEvaluation.length === 0) {
          this.backToList();
        }
      }
    }
  }

  downloadEvaluationExcel() {
    if (!this.evaluations.length) {
      return;
    }

    const worksheet = XLSX.utils.json_to_sheet(this.evaluations.map((evaluation) => ({
      Mois: evaluation.month,
      Année: evaluation.year,
      Filiale: evaluation.filiale,
      Code: evaluation.code,
      Laboratoire: evaluation.laboratoire,
      "Axe d'évaluation": evaluation.axe_evaluation,
      "Critères d'évaluation ( ISO 17025)": evaluation.criteres,
      "Note/20": evaluation.note,
      Pondération: evaluation.ponderation,
      Observations: evaluation.observations,
    })));

    const workbook = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook, worksheet, 'Évaluations');
    XLSX.writeFile(workbook, `evaluations-modifiees-${new Date().toISOString().slice(0, 10)}.xlsx`);
  }

  saveEvaluations() {
    if (!this.evaluations.length) {
      return;
    }

    this.evaluationSaveMessage = '';
    this.evaluationSaveError = '';

    const endpoint = this.userRole === 'general_manager' ? '/api/auth/admin/evaluations/' : '/api/auth/user/evaluations/';
    const body = this.userRole === 'general_manager' ? { evaluations: this.evaluations } : { evaluations: this.evaluations };

    this.http.post<{ saved: number; created: number; updated: number; errors?: string[] }>(
      endpoint,
      body,
      this.httpOptions
    )
      .subscribe({
        next: (response) => {
          if (response.saved > 0) {
            this.evaluationSaveMessage = 'Ajouté avec succès. Les évaluations sont maintenant enregistrées en base et affichées dans l’interface pour modifier la note et l’observation.';
          } else {
            this.evaluationSaveMessage = 'Aucune évaluation n’a été enregistrée.';
          }
          this.evaluationSaveError = response.errors ? response.errors.join(' ') : '';
          this.markEvaluationListsStale();
          this.evaluations = [];
          this.evaluationFileName = '';
          this.showToast(this.evaluationSaveMessage, response.saved > 0 ? 'success' : 'info');
        },
        error: (e) => {
          this.evaluationSaveError = e.error?.errors?.join(' ') || e.error?.detail || 'Erreur lors de l’enregistrement des évaluations.';
          this.evaluationSaveMessage = '';
          this.showToast(this.evaluationSaveError, 'error');
        }
      });
  }

  exportEvaluationPdf() {
    if (!this.evaluationSummaries.length) {
      return;
    }

    const tableRows = this.filteredEvaluations.map((evaluation) => {
      const noteMoyenne = evaluation.note_moyenne !== undefined && evaluation.note_moyenne !== null && evaluation.note_moyenne !== ''
        ? evaluation.note_moyenne
        : '—';
      const conformite = evaluation.conformite_globale !== undefined && evaluation.conformite_globale !== null && evaluation.conformite_globale !== ''
        ? `${evaluation.conformite_globale}%`
        : '—';
      return `
        <tr>
          <td>${evaluation.periode || '—'}</td>
          <td>${evaluation.filiale_name || '—'}</td>
          <td>${evaluation.secteur_name || '—'}</td>
          <td>${evaluation.manager_name || '—'}</td>
          <td>${evaluation.user_name || '—'}</td>
          <td>${noteMoyenne}</td>
          <td>${conformite}</td>
        </tr>
      `;
    }).join('');

    const printWindow = window.open('', '_blank');
    if (!printWindow) {
      this.evaluationError = 'Impossible d’ouvrir la fenêtre d’export PDF.';
      return;
    }

    printWindow.document.write(this.buildPdfDocument(
      'Checklist contrôle laboratoire',
      'Export des évaluations enregistrées dans la base de données',
      `
        <h1>Checklist contrôle laboratoire</h1>
        <p><strong>Utilisateur :</strong> ${this.userFirstName || ''} ${this.userLastName || ''}</p>
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Filiale</th>
              <th>Secteur</th>
              <th>Responsable secteur</th>
              <th>Utilisateur</th>
              <th>Note moyenne /20</th>
              <th>Conformité globale</th>
            </tr>
          </thead>
          <tbody>${tableRows}</tbody>
        </table>
      `
    ));
    printWindow.document.close();
    printWindow.focus();
    printWindow.print();
  }

  loadEvaluations(preserveSaveFeedback = false) {
    if (this.isEvaluationLoading) {
      return;
    }

    const cachedEvaluations = this.readSessionCache<UserEvaluationSummary[]>(this.evaluationSummaryCacheKey);
    if (cachedEvaluations?.length && !this.evaluationSummariesLoaded) {
      this.applyEvaluationSummaries(cachedEvaluations);
    }

    this.evaluationError = '';
    this.evaluationSuccess = '';
    this.isEvaluationLoading = true;
    if (!preserveSaveFeedback) {
      this.evaluationSaveMessage = '';
      this.evaluationSaveError = '';
    }

    const endpoint = this.userRole === 'user' ? '/api/auth/user/evaluations-summary/' : '/api/auth/evaluations-summary/';

    this.http.get<{ evaluations: any[] }>(this.withNoCache(endpoint), this.httpOptions)
      .pipe(
        timeout(this.requestTimeoutMs),
        finalize(() => {
          this.isEvaluationLoading = false;
        })
      )
      .subscribe({
        next: (r) => {
          const evaluations = (r.evaluations || []).map((evaluation) => this.mapEvaluationSummary(evaluation));
          this.applyEvaluationSummaries(evaluations);
          this.writeSessionCache(this.evaluationSummaryCacheKey, evaluations);
          if (this.userRole === 'general_manager' && this.adminSection === 'evaluations') {
            this.markAdminNotificationsAsSeen();
          }
        },
        error: (e) => {
          this.evaluationError = this.getRequestErrorMessage(e, 'Impossible de charger les evaluations.');
          this.showToast(this.evaluationError, 'error');
      },
    });
  }

  openIsoForm() {
    this.showIsoForm = true;
    this.isChecklistMode = false;
    this.evaluationError = '';
    this.evaluationSuccess = '';
    this.evaluationSaveMessage = '';
    this.evaluationSaveError = '';
  }

  openChecklist() {
    this.showIsoForm = false;
    this.isChecklistMode = true;
    this.evaluationError = '';
    this.evaluationSuccess = '';
    this.evaluationSaveMessage = '';
    this.evaluationSaveError = '';

    const months = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin', 'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre'];
    const currentYear = new Date().getFullYear();
    this.checklistMonth = months[new Date().getMonth()] || 'Janvier';
    this.checklistYear = String(currentYear);

    this.http.get('/api/auth/user/checklist-template/', { responseType: 'arraybuffer' }).subscribe({
      next: (data: ArrayBuffer) => {
        const workbook = XLSX.read(data, { type: 'array' });
        const sheet = workbook.Sheets[workbook.SheetNames[0]];
        const rows = XLSX.utils.sheet_to_json<any[]>(sheet, { header: 1, defval: '' });

        const axes: ChecklistAxe[] = [];
        let currentAxeTitle = '';
        let currentCriteria: ChecklistCriterion[] = [];

        for (let i = 4; i < rows.length; i++) {
          const row = rows[i] || [];
          const axe = String(row[6] || '').trim();
          const critere = String(row[7] || '').trim();
          const ponderation = String(row[9] || '').trim();
          const weight = parseFloat(ponderation) || 0;

          if (axe) {
          if (currentAxeTitle && currentCriteria.length) {
            axes.push({
              id: axes.length,
              title: currentAxeTitle,
              criteria: currentCriteria,
            });
          }
            currentAxeTitle = axe;
            currentCriteria = [];
          }
          if (critere) {
            currentCriteria.push({
              text: critere,
              weight: weight > 0 ? weight : 1,
              note: '',
              obs: '',
            });
          }
        }

        if (currentAxeTitle && currentCriteria.length) {
          axes.push({
            id: axes.length,
            title: currentAxeTitle,
            criteria: currentCriteria,
          });
        }

        this.checklistAxes = axes;
        this.evaluationSuccess = `${axes.reduce((sum, axe) => sum + axe.criteria.length, 0)} critère(s) chargé(s) depuis le fichier Excel.`;
      },
      error: () => {
        this.evaluationError = 'Impossible de charger le fichier Excel de checklist.';
        this.isChecklistMode = false;
      },
    });
  }

  saveChecklist() {
    if (!this.checklistAxes.length) {
      this.evaluationError = 'Aucun critère à enregistrer.';
      return;
    }

    const evaluations: any[] = [];
    for (const axe of this.checklistAxes) {
      for (const cri of axe.criteria) {
        const noteValue = cri.note != null && cri.note !== '' ? String(cri.note) : '';
        const obsValue = cri.obs || '';
        if (noteValue || obsValue) {
          evaluations.push({
            month: this.checklistMonth,
            year: this.checklistYear,
            filiale: '',
            code: '',
            laboratoire: '',
            axe_evaluation: axe.title,
            criteres: cri.text,
            note: noteValue,
            ponderation: String(cri.weight),
            observations: obsValue,
          });
        }
      }
    }

    if (!evaluations.length) {
      this.evaluationError = 'Remplissez au moins une note ou observation.';
      return;
    }

    this.evaluationSaveMessage = '';
    this.evaluationSaveError = '';

    const endpoint = this.userRole === 'general_manager' ? '/api/auth/admin/evaluations/' : '/api/auth/user/evaluations/';
    const body = this.userRole === 'general_manager' ? { evaluations } : { evaluations };

    this.http.post<{ saved: number; created: number; updated: number; errors?: string[] }>(
      endpoint,
      body,
      this.httpOptions
    ).subscribe({
      next: (response) => {
        this.evaluationSaveMessage = response.saved > 0
          ? 'Évaluation enregistrée avec succès.'
          : 'Aucune évaluation n’a été enregistrée.';
        this.evaluationSaveError = response.errors ? response.errors.join(' ') : '';
        this.isChecklistMode = false;
        this.checklistAxes = [];
        this.loadEvaluations(true);
      },
      error: (e) => {
        this.evaluationSaveError = e.error?.errors?.join(' ') || e.error?.detail || 'Erreur lors de l’enregistrement.';
      },
    });
  }

  toggleAxe(axe: ChecklistAxe) {
    axe.collapsed = !axe.collapsed;
  }

  getChecklistAxeScore(axe: ChecklistAxe): number {
    const filled = axe.criteria.filter(c => c.note && !isNaN(parseFloat(c.note)));
    if (filled.length !== axe.criteria.length) return 0;
    const weightedSum = filled.reduce((sum, c) => sum + (parseFloat(c.note!) * c.weight), 0);
    const maxPossible = axe.criteria.reduce((sum, c) => sum + (20 * c.weight), 0);
    return maxPossible > 0 ? (weightedSum / maxPossible) * 20 : 0;
  }

  getChecklistAxeTotal(axe: ChecklistAxe): number {
    return axe.criteria.reduce((sum, c) => {
      const num = parseFloat(c.note || '0');
      return sum + (!isNaN(num) && num >= 0 && num <= 20 ? num * c.weight : 0);
    }, 0);
  }

  getChecklistAxeFilled(axe: ChecklistAxe): number {
    return axe.criteria.filter(c => c.note && !isNaN(parseFloat(c.note)) && parseFloat(c.note) >= 0 && parseFloat(c.note) <= 20).length;
  }

  getChecklistCriterionWeighted(cri: ChecklistCriterion): string {
    const num = parseFloat(cri.note || '');
    if (isNaN(num) || num < 0 || num > 20) return '—';
    return (num * cri.weight).toFixed(1);
  }

  get checklistTotalWeighted(): number {
    let total = 0;
    for (const axe of this.checklistAxes) {
      for (const cri of axe.criteria) {
        const num = parseFloat(cri.note || '');
        if (!isNaN(num) && num >= 0 && num <= 20) {
          total += num * cri.weight;
        }
      }
    }
    return total;
  }

  get checklistFilledCount(): number {
    return this.checklistAxes.reduce((sum, axe) => sum + this.getChecklistAxeFilled(axe), 0);
  }

  get checklistTotalCount(): number {
    return this.checklistAxes.reduce((sum, axe) => sum + axe.criteria.length, 0);
  }

  get checklistGlobalScoreDisplay(): string {
    const filled = this.checklistFilledCount;
    const total = this.checklistTotalCount;
    const score = this.checklistGlobalScore;
    if (score !== null && filled === total && total > 0) return score.toFixed(1);
    return '—';
  }

  updateChecklistNote(axe: ChecklistAxe, index: number) {
    const cri = axe.criteria[index];
    const num = parseFloat(cri.note || '');
    if (isNaN(num) || num < 0 || num > 20) {
      cri.note = '';
    } else {
      cri.note = String(Math.min(20, Math.max(0, num)));
    }
  }

  cancelChecklist() {
    this.isChecklistMode = false;
    this.showIsoForm = false;
    this.checklistAxes = [];
    this.checklistItems = [];
    this.evaluationError = '';
  }

  saveIsoForm(evaluations: any[]) {
    if (!evaluations || !evaluations.length) {
      return;
    }

    this.evaluationSaveMessage = '';
    this.evaluationSaveError = '';

    const endpoint = this.userRole === 'general_manager' ? '/api/auth/admin/evaluations/' : '/api/auth/user/evaluations/';
    const body = this.userRole === 'general_manager' ? { evaluations } : { evaluations };

    this.http.post<{ saved: number; created: number; updated: number; errors?: string[] }>(
      endpoint,
      body,
      this.httpOptions
    ).subscribe({
      next: (response) => {
        this.evaluationSaveMessage = response.saved > 0
          ? 'Évaluation enregistrée avec succès.'
          : 'Aucune évaluation n\'a été enregistrée.';
        this.evaluationSaveError = response.errors ? response.errors.join(' ') : '';
        this.showIsoForm = false;
        this.markEvaluationListsStale();
        this.showToast(this.evaluationSaveMessage, response.saved > 0 ? 'success' : 'info');
      },
      error: (e) => {
        this.evaluationSaveError = e.error?.errors?.join(' ') || e.error?.detail || 'Erreur lors de l\'enregistrement.';
        this.showToast(this.evaluationSaveError, 'error');
      },
    });
  }

  onAvatarChange(event: Event) {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files[0]) {
      this.avatarFile = input.files[0];
      const reader = new FileReader();
      reader.onload = (e) => {
        this.userAvatar = e.target?.result as string;
      };
      reader.readAsDataURL(this.avatarFile);
    }
  }

  saveProfile() {
    if (this.profileSaving) {
      return;
    }

    this.profileSaving = true;
    if (this.avatarFile) {
      const formData = new FormData();
      formData.append('first_name', this.userFirstName);
      formData.append('last_name', this.userLastName);
      formData.append('email', this.userEmail);
      formData.append('avatar', this.avatarFile);

      this.http.post('/api/auth/user/profile/', formData, {
        ...this.httpOptions,
        reportProgress: true,
      }).pipe(
        timeout(this.requestTimeoutMs),
        finalize(() => {
          this.profileSaving = false;
        })
      ).subscribe({
        next: (r: any) => {
          this.userFirstName = r.first_name || this.userFirstName;
          this.userLastName = r.last_name || this.userLastName;
          this.userEmail = r.email || this.userEmail;
          this.userAvatar = r.avatar || this.userAvatar;
          this.avatarFile = null;
          this.isProfileEditing = false;
          this.profileSuccess = 'Profil mis à jour avec succès.';
          this.profileError = '';
          this.showToast(this.profileSuccess, 'success');
        },
        error: (e) => {
          this.profileError = this.getRequestErrorMessage(e, 'Erreur lors de la mise a jour du profil.');
          this.profileSuccess = '';
          this.showToast(this.profileError, 'error');
        },
      });
      return;
    }

    this.http.post('/api/auth/user/profile/', {
      first_name: this.userFirstName,
      last_name: this.userLastName,
      email: this.userEmail,
    }, this.httpOptions).pipe(
      timeout(this.requestTimeoutMs),
      finalize(() => {
        this.profileSaving = false;
      })
    ).subscribe({
      next: (r: any) => {
        this.userFirstName = r.first_name || this.userFirstName;
        this.userLastName = r.last_name || this.userLastName;
        this.userEmail = r.email || this.userEmail;
        this.userAvatar = r.avatar || this.userAvatar;
        this.isProfileEditing = false;
        this.profileSuccess = 'Profil mis à jour avec succès.';
        this.profileError = '';
        this.showToast(this.profileSuccess, 'success');
      },
      error: (e) => {
        this.profileError = this.getRequestErrorMessage(e, 'Erreur lors de la mise a jour du profil.');
        this.profileSuccess = '';
        this.showToast(this.profileError, 'error');
      },
    });
  }

  get filteredEvaluations(): UserEvaluationSummary[] {
    return this.evaluationSummaries.filter((evaluation) => {
      if (this.evaluationSearch.trim()) {
        const search = this.evaluationSearch.trim().toLocaleLowerCase('fr');
        const haystack = [
          evaluation.periode,
          evaluation.filiale_name,
          evaluation.secteur_name,
          evaluation.manager_name,
          evaluation.user_name,
        ].join(' ').toLocaleLowerCase('fr');
        if (!haystack.includes(search)) {
          return false;
        }
      }
      if (this.evaluationDateFilter) {
        if (evaluation.periode !== this.evaluationDateFilter) {
          return false;
        }
      }
      if (this.evaluationSectorFilter && Number(evaluation.sector_id || 0) !== this.evaluationSectorFilter) {
        return false;
      }
      if (this.evaluationManagerFilter && Number(evaluation.manager_id || 0) !== this.evaluationManagerFilter) {
        return false;
      }
      if (this.evaluationFilialeFilter && Number(evaluation.filiale_id || 0) !== this.evaluationFilialeFilter) {
        return false;
      }
      if (this.evaluationLaboratoireFilter && evaluation.laboratoire_name !== this.evaluationLaboratoireFilter) {
        return false;
      }
      if (this.evaluationUserFilter && Number(evaluation.user_id || 0) !== this.evaluationUserFilter) {
        return false;
      }
      return true;
    });
  }

  get evaluationAvgScore(): number {
    const notes = this.filteredEvaluations
      .map((ev: any) => parseFloat(String(ev.note_moyenne ?? '').replace(',', '.')))
      .filter((n) => !Number.isNaN(n));
    if (!notes.length) return 0;
    return Math.round((notes.reduce((a, b) => a + b, 0) / notes.length) * 100) / 100;
  }

  get evaluationConformityAvg(): number {
    const confs = this.filteredEvaluations
      .map((ev: any) => parseFloat(String(ev.conformite_globale ?? '').replace(',', '.')))
      .filter((n) => !Number.isNaN(n));
    if (!confs.length) return 0;
    return Math.round((confs.reduce((a, b) => a + b, 0) / confs.length) * 100) / 100;
  }

  get evaluationFiltraCount(): number {
    const filiales = new Set<string>();
    for (const ev of this.filteredEvaluations as any[]) {
      const name = ev.filiale_name || '';
      if (name) filiales.add(name);
    }
    return filiales.size;
  }

  private extractEvaluationFilters(evaluations: UserEvaluationSummary[]) {
    const dateSet = new Set<string>();
    const laboratoireSet = new Set<string>();
    const managerMap = new Map<number, string>();
    for (const evaluation of evaluations) {
      const periode = evaluation.periode || [evaluation.mois, evaluation.annee].filter(Boolean).join(' ').trim();
      if (periode) {
        dateSet.add(periode);
      }
      if (evaluation.laboratoire_name && evaluation.laboratoire_name !== '—') {
        laboratoireSet.add(evaluation.laboratoire_name);
      }
      if (evaluation.manager_id && evaluation.manager_name && evaluation.manager_name !== '—') {
        managerMap.set(Number(evaluation.manager_id), evaluation.manager_name);
      }
    }
    this.evaluationDates = Array.from(dateSet).sort();
    this.evaluationLaboratoires = Array.from(laboratoireSet).sort();
    this.evaluationManagers = Array.from(managerMap.entries())
      .map(([id, name]) => ({ id, name }))
      .sort((left, right) => left.name.localeCompare(right.name, 'fr', { sensitivity: 'base' }));
  }

  get evaluationsEndpoint(): string {
    return this.userRole === 'general_manager' ? '/api/auth/admin/evaluations/' : '/api/auth/user/evaluations/';
  }

  saveEvaluationRow(evaluation: EvaluationRow) {
    evaluation.isSaving = true;
    this.evaluationSaveMessage = '';
    this.evaluationSaveError = '';

    const payload: any = {
      id: evaluation.id || undefined,
      month: evaluation.month,
      year: evaluation.year,
      filiale: evaluation.filiale || evaluation.filiale_name || '',
      code: evaluation.code,
      laboratoire: evaluation.laboratoire || evaluation.laboratoire_name || '',
      axe_evaluation: evaluation.axe_evaluation,
      criteres: evaluation.criteres,
      note: evaluation.note,
      ponderation: evaluation.ponderation,
      observations: evaluation.observations,
    };

    if (!evaluation.line_pk) {
      const endpoint = this.userRole === 'general_manager' ? '/api/auth/admin/evaluations/' : '/api/auth/user/evaluations/';
      const body = this.userRole === 'general_manager' ? { evaluations: [payload] } : { evaluation: payload };
      this.http.post<{ saved: number; created: number; updated: number; errors?: string[] }>(
        endpoint,
        body,
        this.httpOptions
      ).pipe(
        timeout(this.requestTimeoutMs),
        finalize(() => {
          evaluation.isSaving = false;
        })
      ).subscribe({
         next: (response) => {
          evaluation.editing = false;
          evaluation.isNew = false;
          this.evaluationSaveMessage = response.saved > 0
            ? 'Ajouté avec succès.'
            : 'Aucune évaluation n\'a été enregistrée.';
          this.evaluationSaveError = response.errors ? response.errors.join(' ') : '';
          this.markEvaluationListsStale();
          this.showToast(this.evaluationSaveMessage, response.saved > 0 ? 'success' : 'info');
          if (this.userRole === 'user' && this.isEvaluationDetailMode) {
            this.backToList();
          }
        },
        error: (e) => {
          evaluation.editing = false;
          this.evaluationSaveError = this.getRequestErrorMessage(e, 'Erreur lors de l’enregistrement de l’évaluation.');
          this.showToast(this.evaluationSaveError, 'error');
        }
      });
      return;
    }

    const detailEndpoint = this.userRole === 'general_manager'
      ? `/api/auth/admin/evaluations/${evaluation.line_pk}/`
      : `/api/auth/user/evaluations/${evaluation.line_pk}/`;
    this.http.patch<{ id: number; note: string; observations: string; tx_conformite?: string }>(
      detailEndpoint,
      {
        note: evaluation.note,
        observations: evaluation.observations,
      },
      this.httpOptions
    ).pipe(
      timeout(this.requestTimeoutMs),
      finalize(() => {
        evaluation.isSaving = false;
      })
    ).subscribe({
        next: (response) => {
          evaluation.note = response.note || '';
          evaluation.observations = response.observations || '';
          evaluation.tx_conformite = response.tx_conformite || evaluation.tx_conformite || '';
          evaluation.editing = false;
          this.evaluationSaveMessage = 'Modification enregistrée avec succès.';
          this.markEvaluationListsStale();
          this.showToast(this.evaluationSaveMessage, 'success');
        },
      error: (e) => {
        evaluation.editing = false;
        this.evaluationSaveError = this.getRequestErrorMessage(e, 'Erreur lors de la mise a jour de l’evaluation.');
        this.showToast(this.evaluationSaveError, 'error');
      }
    });
  }

  deleteEvaluation(evaluation: EvaluationRow, index: number) {
    this.evaluationSaveMessage = '';
    this.evaluationSaveError = '';

    const targetRows = this.isEvaluationDetailMode ? this.selectedEvaluation : this.evaluations;

    if (!evaluation.line_pk) {
      targetRows.splice(index, 1);
      this.sortEvaluations();
      this.evaluationSaveMessage = 'Ligne importée retirée avant enregistrement.';
      this.showToast(this.evaluationSaveMessage, 'info');
      return;
    }

    evaluation.isDeleting = true;
    const detailEndpoint = this.userRole === 'general_manager'
      ? `/api/auth/admin/evaluations/${evaluation.line_pk}/`
      : `/api/auth/user/evaluations/${evaluation.line_pk}/`;
    this.http.delete<{ deleted: boolean }>(
      detailEndpoint,
      this.httpOptions
    ).pipe(
      timeout(this.requestTimeoutMs),
      finalize(() => {
        evaluation.isDeleting = false;
      })
    ).subscribe({
      next: () => {
        targetRows.splice(index, 1);
        this.evaluationSaveMessage = 'Évaluation supprimée.';
        this.markEvaluationListsStale();
        this.showToast(this.evaluationSaveMessage, 'success');
        if (this.isEvaluationDetailMode && this.selectedEvaluation.length === 0) {
          this.backToList();
        }
      },
      error: (e) => {
        this.evaluationSaveError = this.getRequestErrorMessage(e, 'Erreur lors de la suppression de l’évaluation.');
        this.showToast(this.evaluationSaveError, 'error');
      }
    });
  }


  get filteredBranches() {
    const search = this.branchSearch.trim().toLowerCase();
    if (!search) {
      return this.branches;
    }
    return this.branches.filter((branch) =>
      branch.code.toString().includes(search) ||
      branch.name.toLowerCase().includes(search) ||
      branch.sector.toLowerCase().includes(search)
    );
  }

  get filteredSectors() {
    const search = this.sectorSearch.trim().toLowerCase();
    if (!search) {
      return this.sectors;
    }
    return this.sectors.filter((sector) => sector.name.toLowerCase().includes(search));
  }

  get filteredLaboratories() {
    const search = this.laboratorySearch.trim().toLowerCase();
    if (!search) {
      return this.laboratories;
    }
    return this.laboratories.filter((laboratory) => laboratory.name.toLowerCase().includes(search));
  }

  selectAdminSection(section: 'home' | 'branches' | 'sectors' | 'users' | 'managers' | 'evaluations' | 'laboratories' | 'ai') {
    this.adminSection = section;
    this.branchSearch = '';
    this.sectorSearch = '';
    this.userSearch = '';
    this.laboratorySearch = '';
    this.error = '';
    this.mlPredictionError = '';
    if (section === 'branches') {
      this.resetBranchForm();
    }
    if (section === 'sectors') {
      this.resetSectorForm();
    }
    if (section === 'users' || section === 'managers') {
      this.adminUserFilter = 'all';
      this.resetUserForm();
    }
    if (section === 'laboratories') {
      this.resetLaboratoryForm();
      if (!this.scopeDataLoaded) {
        this.loadScope(false, true);
      }
      if (!this.laboratoriesLoaded) {
        this.loadLaboratories();
      }
    }
    if ((section === 'home' || section === 'branches' || section === 'sectors' || section === 'users' || section === 'managers') && !this.scopeDataLoaded) {
      this.loadScope(false, true);
    }
    if (section === 'home' && (this.userRole === 'general_manager' || this.userRole === 'sector_manager')) {
      this.loadEvaluationOverview();
    }
    if (section === 'evaluations') {
      this.loadEvaluationOverview();
      if (!this.evaluationSummariesLoaded || this.evaluationSummariesStale) {
        this.loadEvaluations();
      } else {
        this.markAdminNotificationsAsSeen();
      }
    }
    if (section === 'ai') {
      if (!this.scopeDataLoaded) {
        this.loadScope(false, true);
      }
      this.initializeAdminAiWorkspace();
      this.aiWorkspaceMode = 'predict';
    }

    if (section === 'users' || section === 'managers') {
      this.markAdminUserNotificationsAsSeen();
    }
  }

  selectUserSection(section: 'home' | 'profile' | 'secteur' | 'evaluations' | 'sector_users') {
    this.userSection = section;
    this.error = '';
    this.profileError = '';
    this.profileSuccess = '';
    this.passwordError = '';
    this.passwordSuccess = '';
    this.showPasswordForm = false;
    this.isProfileEditing = false;
    this.isChecklistMode = false;
    this.isEvaluationDetailMode = false;
    this.isEvaluationFormMode = false;
    this.selectedEvaluation = [];
    this.selectedEvaluationTitle = '';
    if (section === 'evaluations') {
      if (this.userRole === 'sector_manager') {
        this.resetEvaluationFilters();
      }
      if (this.userRole === 'user') {
        if (!this.userEvaluationListLoaded || this.userEvaluationListStale) {
          this.loadUserEvaluationList();
        }
      } else {
        if (!this.scopeDataLoaded) {
          this.loadScope(false, true);
        }
        if (!this.evaluationSummariesLoaded || this.evaluationSummariesStale) {
          this.loadEvaluations();
        }
      }
    }
    if (section === 'sector_users' && !this.scopeDataLoaded) {
      this.loadScope(false, true);
    }
    if (section === 'profile') {
      this.loadUserProfile();
    }
  }

  loadUserProfile() {
    this.http.get<any>(this.withNoCache('/api/auth/user/profile/'), this.httpOptions).subscribe({
      next: (r) => {
        this.userFirstName = r.first_name || '';
        this.userLastName = r.last_name || '';
        this.userEmail = r.email || '';
         this.userBranchName = r.branch_name || '';
         this.userBranchCode = r.branch_code || null;
        this.userSectorName = r.sector_name || '';
        this.userAvatar = r.avatar || '';
      },
      error: () => {
        this.userFirstName = this.userFirstName || '';
        this.userLastName = this.userLastName || '';
        this.userEmail = this.userEmail || '';
      },
    });
  }

  editProfile() {
    this.userEmail = this.userEmail || '';
    this.isProfileEditing = true;
    this.profileError = '';
    this.profileSuccess = '';
  }

  cancelProfileEdit() {
    this.isProfileEditing = false;
    this.profileError = '';
    this.profileSuccess = '';
    this.loadUserProfile();
  }

  changePassword() {
    if (this.passwordSaving) {
      return;
    }

    this.passwordSaving = true;
    this.http.post('/api/auth/user/password/', {
      current_password: this.currentPassword,
      new_password: this.newPassword,
    }, this.httpOptions).pipe(
      timeout(this.requestTimeoutMs),
      finalize(() => {
        this.passwordSaving = false;
      })
    ).subscribe({
      next: () => {
        this.passwordSuccess = 'Mot de passe modifié avec succès.';
        this.passwordError = '';
        this.currentPassword = '';
        this.newPassword = '';
        this.showPasswordForm = false;
        this.showToast(this.passwordSuccess, 'success');
      },
      error: (e) => {
        this.passwordError = this.getRequestErrorMessage(e, 'Erreur lors du changement de mot de passe.');
        this.passwordSuccess = '';
        this.showToast(this.passwordError, 'error');
      },
    });
  }

  private resetBranchForm() {
    this.branchForm = { id: null, code: null, name: '', sectorId: null, laboratoireId: null };
    this.isBranchEditing = false;
    this.sectorChangeBranchId = null;
    this.sectorChangeSectorId = null;
    this.error = '';
  }

  private resetSectorForm() {
    this.sectorForm = { id: null, name: '', managerId: null };
    this.isSectorEditing = false;
    this.error = '';
  }

  private scrollToAdminForm(selector: string) {
    setTimeout(() => {
      const formElement = document.querySelector(selector) as HTMLElement | null;
      if (!formElement) {
        return;
      }

      formElement.scrollIntoView({ behavior: 'smooth', block: 'start' });

      const firstField = formElement.querySelector('input, select, textarea') as HTMLElement | null;
      if (firstField) {
        setTimeout(() => firstField.focus(), 180);
      }
    }, 0);
  }

  addNewBranch() {
    this.adminSection = 'branches';
    this.resetBranchForm();
    this.isBranchEditing = false;
    this.scrollToAdminForm('#adminBranchForm');
  }

  addNewSector() {
    this.adminSection = 'sectors';
    this.resetSectorForm();
    this.isSectorEditing = false;
    this.scrollToAdminForm('#adminSectorForm');
  }

  editBranch(branch: { id: number; code: number; name: string; sector: string; sectorId: number; laboratoireId: number | null; laboratoireName: string }) {
    this.adminSection = 'branches';
    this.branchForm = { id: branch.id, code: branch.code, name: branch.name, sectorId: branch.sectorId, laboratoireId: branch.laboratoireId };
    this.isBranchEditing = true;
    this.error = '';
    this.scrollToAdminForm('#adminBranchForm');
  }

  editSector(sector: { id: number; name: string; managerId: number | null }) {
    this.adminSection = 'sectors';
    this.sectorForm = { id: sector.id, name: sector.name, managerId: sector.managerId };
    this.isSectorEditing = true;
    this.error = '';
    this.scrollToAdminForm('#adminSectorForm');
  }

  saveBranch() {
    if (this.adminFormSaving) {
      return;
    }

    const { id, code, name, sectorId, laboratoireId } = this.branchForm;
    if (!code || !name.trim() || !sectorId) {
      this.error = 'Le code, le nom et le secteur sont requis.';
      return;
    }

    const duplicateCode = this.branches.some((branch) => branch.code === code && branch.id !== id);
    if (duplicateCode) {
      this.error = 'Le code de filiale doit être unique.';
      return;
    }

    const selectedSectorId = Number(this.branchForm.sectorId);
    if (!selectedSectorId || Number.isNaN(selectedSectorId)) {
      this.error = 'Vous devez sélectionner un secteur valide.';
      return;
    }

    const selectedSectorName = this.sectors.find((sector) => sector.id === selectedSectorId)?.name || '';
    const selectedLaboratoire = this.laboratories.find((laboratoire) => laboratoire.id === laboratoireId);
    const payload: any = { code, name: name.trim(), sector_id: selectedSectorId };
    if (laboratoireId) {
      payload.laboratoire_id = laboratoireId;
    }

    this.adminFormSaving = true;
    if (this.isBranchEditing && id !== null) {
      this.http.patch(`/api/auth/admin/branches/${id}/`, payload, this.httpOptions).pipe(
        timeout(this.requestTimeoutMs),
        finalize(() => {
          this.adminFormSaving = false;
        })
      ).subscribe({
        next: (updated: any) => {
          const index = this.branches.findIndex((branch) => branch.id === id);
          if (index > -1) {
            this.branches[index] = {
              id,
              code,
              name: name.trim(),
              sector: updated.sector_name || selectedSectorName,
              sectorId: selectedSectorId,
              laboratoireId: updated.laboratoire_id || null,
              laboratoireName: updated.laboratoire_name || selectedLaboratoire?.name || '',
            };
          }
          this.resetBranchForm();
          this.showToast('Filiale modifiée avec succès.', 'success');
        },
        error: (e) => {
          this.error = this.getRequestErrorMessage(e, 'Erreur lors de la mise a jour de la filiale.');
          this.showToast(this.error, 'error');
        },
      });
    } else {
      this.http.post(`/api/auth/admin/branches/`, payload, this.httpOptions).pipe(
        timeout(this.requestTimeoutMs),
        finalize(() => {
          this.adminFormSaving = false;
        })
      ).subscribe({
        next: (created: any) => {
          this.branches.push({
            id: created.id,
            code: created.code,
            name: created.name,
            sector: created.sector_name,
            sectorId: created.sector_id || selectedSectorId,
            laboratoireId: created.laboratoire_id || null,
            laboratoireName: created.laboratoire_name || selectedLaboratoire?.name || '',
          });
          this.resetBranchForm();
          this.showToast('Filiale ajoutée avec succès.', 'success');
        },
        error: (e) => {
          this.error = this.getRequestErrorMessage(e, 'Erreur lors de la creation de la filiale.');
          this.showToast(this.error, 'error');
        },
      });
    }
  }

  saveSector() {
    if (this.adminFormSaving) {
      return;
    }

    const { id, name, managerId } = this.sectorForm;
    if (!name.trim() || !managerId) {
      this.error = 'Le nom du secteur et le responsable sont requis.';
      return;
    }

    const payload = { name: name.trim(), manager_id: managerId };
    this.adminFormSaving = true;
    if (this.isSectorEditing && id !== null) {
      this.http.patch(`/api/auth/admin/sectors/${id}/`, payload, this.httpOptions).pipe(
        timeout(this.requestTimeoutMs),
        finalize(() => {
          this.adminFormSaving = false;
        })
      ).subscribe({
        next: (updated: any) => {
          const index = this.sectors.findIndex((sector) => sector.id === id);
          if (index > -1) {
            this.sectors[index] = {
              id,
              name: updated.name,
              managerId: updated.manager_id,
              managerName: updated.manager_name || this.sectors[index].managerName,
            };
          }
          this.resetSectorForm();
          this.showToast('Secteur modifié avec succès.', 'success');
        },
        error: (e) => {
          this.error = this.getRequestErrorMessage(e, 'Erreur lors de la mise a jour du secteur.');
          this.showToast(this.error, 'error');
        },
      });
    } else {
      this.http.post(`/api/auth/admin/sectors/`, payload, this.httpOptions).pipe(
        timeout(this.requestTimeoutMs),
        finalize(() => {
          this.adminFormSaving = false;
        })
      ).subscribe({
        next: (created: any) => {
          this.sectors.push({
            id: created.id,
            name: created.name,
            managerId: created.manager_id,
            managerName: created.manager_name || '',
          });
          this.resetSectorForm();
          this.showToast('Secteur ajouté avec succès.', 'success');
        },
        error: (e) => {
          this.error = this.getRequestErrorMessage(e, 'Erreur lors de la creation du secteur.');
          this.showToast(this.error, 'error');
        },
      });
    }
  }

  loadLaboratories() {
    this.http.get<{ laboratoires: Array<{ id: number; name: string }> }>(this.withNoCache('/api/auth/admin/laboratoires/'), this.httpOptions)
      .subscribe({
        next: (r) => {
          this.laboratories = r.laboratoires || [];
          this.laboratoriesLoaded = true;
        },
        error: (e) => this.error = e.error?.detail || 'Impossible de charger les laboratoires.',
      });
  }

  addNewLaboratory() {
    this.adminSection = 'laboratories';
    this.resetLaboratoryForm();
    this.isLaboratoryEditing = false;
    this.scrollToAdminForm('#adminLaboratoryForm');
  }

  editLaboratory(laboratory: { id: number; name: string }) {
    this.adminSection = 'laboratories';
    this.laboratoryForm = { id: laboratory.id, name: laboratory.name };
    this.isLaboratoryEditing = true;
    this.error = '';
    this.scrollToAdminForm('#adminLaboratoryForm');
  }

  saveLaboratory() {
    if (this.adminFormSaving) {
      return;
    }

    const { id, name } = this.laboratoryForm;
    if (!name.trim()) {
      this.error = 'Le nom du laboratoire est requis.';
      return;
    }

    const payload = { name: name.trim() };
    this.adminFormSaving = true;

    if (this.isLaboratoryEditing && id !== null) {
      this.http.patch(`/api/auth/admin/laboratoires/${id}/`, payload, this.httpOptions).pipe(
        timeout(this.requestTimeoutMs),
        finalize(() => {
          this.adminFormSaving = false;
        })
      ).subscribe({
        next: (updated: any) => {
          const index = this.laboratories.findIndex((laboratory) => laboratory.id === id);
          if (index > -1) {
            this.laboratories[index] = { id, name: updated.name };
          }
          this.resetLaboratoryForm();
          this.showToast('Laboratoire modifié avec succès.', 'success');
        },
        error: (e) => {
          this.error = this.getRequestErrorMessage(e, 'Erreur lors de la mise a jour du laboratoire.');
          this.showToast(this.error, 'error');
        },
      });
    } else {
      this.http.post(`/api/auth/admin/laboratoires/`, payload, this.httpOptions).pipe(
        timeout(this.requestTimeoutMs),
        finalize(() => {
          this.adminFormSaving = false;
        })
      ).subscribe({
        next: (created: any) => {
          this.laboratories.push({
            id: created.id,
            name: created.name,
          });
          this.resetLaboratoryForm();
          this.showToast('Laboratoire ajouté avec succès.', 'success');
        },
        error: (e) => {
          this.error = this.getRequestErrorMessage(e, 'Erreur lors de la creation du laboratoire.');
          this.showToast(this.error, 'error');
        },
      });
    }
  }

  deleteLaboratory(laboratoireId: number) {
    if (!confirm('Supprimer ce laboratoire ?')) {
      return;
    }
    this.http.delete(`/api/auth/admin/laboratoires/${laboratoireId}/`, this.httpOptions).subscribe({
      next: () => {
        this.laboratories = this.laboratories.filter((laboratory) => laboratory.id !== laboratoireId);
        this.showToast('Laboratoire supprimé avec succès.', 'success');
      },
      error: (e) => {
        this.error = e.error?.detail || 'Erreur lors de la suppression du laboratoire.';
        this.showToast(this.error, 'error');
      },
    });
  }

  private resetLaboratoryForm() {
    this.laboratoryForm = { id: null, name: '' };
    this.isLaboratoryEditing = false;
    this.error = '';
  }

  cancelLaboratoryForm() {
    this.resetLaboratoryForm();
  }

  private resetUserForm() {
    this.userForm = {
      id: null,
      email: '',
      first_name: '',
      last_name: '',
      password: '',
      role: 'user',
      branch_id: null,
      managed_sector_id: null,
    };
    this.isUserEditing = false;
    this.error = '';
  }

  addNewUser(role: 'user' | 'sector_manager' = 'user') {
    this.adminSection = 'users';
    this.resetUserForm();
    this.userForm.role = role;
    this.adminUserFilter = role;
    this.scrollToAdminForm('#adminAccountForm');
  }

  editUser(user: { id: number; email: string; first_name: string; last_name: string; role: string; branch_id?: number | null; managed_sector_id?: number | null }) {
    this.adminSection = 'users';
    if (user.role === 'user' || user.role === 'sector_manager') {
      this.adminUserFilter = user.role;
    }
    this.userForm = {
      id: user.id,
      email: user.email,
      first_name: user.first_name || '',
      last_name: user.last_name || '',
      password: '',
      role: user.role,
      branch_id: user.branch_id || null,
      managed_sector_id: user.managed_sector_id || null,
    };
    this.isUserEditing = true;
    this.error = '';
    this.scrollToAdminForm('#adminAccountForm');
  }

  saveUser() {
    if (this.adminFormSaving) {
      return;
    }

    const { id, email, first_name, last_name, password, role, branch_id, managed_sector_id } = this.userForm;
    if (!email.trim() || !first_name.trim() || !last_name.trim() || !role) {
      this.error = 'Email, prénom, nom et rôle sont requis.';
      return;
    }

    if (role === 'user' && !branch_id) {
      this.error = 'La filiale est requise pour les utilisateurs.';
      return;
    }

    if (role === 'sector_manager' && !managed_sector_id && !this.isUserEditing) {
      this.error = 'Affecter un secteur au responsable est recommandé.';
      return;
    }

    const payload: any = {
      email: email.trim(),
      first_name: first_name.trim(),
      last_name: last_name.trim(),
      role,
      branch_id: branch_id || null,
      managed_sector_id: managed_sector_id || null,
    };

    if (!this.isUserEditing) {
      if (!password || password.length < 8) {
        this.error = 'Le mot de passe doit contenir au moins 8 caractères.';
        return;
      }
      payload.password = password;
    } else if (password) {
      payload.password = password;
    }

    this.adminFormSaving = true;
    if (this.isUserEditing && id !== null) {
      this.http.patch(`/api/auth/admin/users/${id}/`, payload, this.httpOptions).pipe(
        timeout(this.requestTimeoutMs),
        finalize(() => {
          this.adminFormSaving = false;
        })
      ).subscribe({
        next: (updated: any) => {
          const updatedUser = {
            id: updated.id,
            email: updated.email,
            first_name: updated.first_name,
            last_name: updated.last_name,
            role: updated.role,
            branch_id: updated.branch_id,
            branch__name: updated.branch_name || null,
            branch__sector__name: this.branches.find((branch) => branch.id === updated.branch_id)?.sector || null,
            managed_sector_id: updated.managed_sector_id || null,
            managed_sector__name: updated.managed_sector_name || null,
            is_active: updated.is_active,
          };

          const existingUserIndex = this.users.findIndex((user) => user.id === id);
          if (existingUserIndex > -1) {
            if (updated.role === 'user') {
              this.users[existingUserIndex] = updatedUser;
            } else {
              this.users.splice(existingUserIndex, 1);
            }
          }

          const existingManagerIndex = this.sectorManagers.findIndex((user) => user.id === id);
          if (existingManagerIndex > -1) {
            if (updated.role === 'sector_manager') {
              this.sectorManagers[existingManagerIndex] = updatedUser;
            } else {
              this.sectorManagers.splice(existingManagerIndex, 1);
            }
          }

          if (updated.role === 'user' && existingUserIndex === -1) {
            this.users.push(updatedUser);
          }
          if (updated.role === 'sector_manager' && existingManagerIndex === -1) {
            this.sectorManagers.push(updatedUser);
          }

          this.resetUserForm();
          this.showToast('Utilisateur mis à jour avec succès.', 'success');
        },
        error: (e) => {
          this.error = this.getRequestErrorMessage(e, 'Erreur lors de la mise a jour de l’utilisateur.');
          this.showToast(this.error, 'error');
        },
      });
    } else {
      this.http.post(`/api/auth/admin/users/`, payload, this.httpOptions).pipe(
        timeout(this.requestTimeoutMs),
        finalize(() => {
          this.adminFormSaving = false;
        })
      ).subscribe({
        next: (created: any) => {
          const newUser = {
            id: created.id,
            email: created.email,
            first_name: created.first_name,
            last_name: created.last_name,
            role: created.role,
            branch_id: created.branch_id,
            branch__name: created.branch_name || null,
            branch__sector__name: this.branches.find((branch) => branch.id === created.branch_id)?.sector || null,
            managed_sector_id: created.managed_sector_id || null,
            managed_sector__name: created.managed_sector_name || null,
            is_active: true,
          };
          if (created.role === 'user') {
            this.users.push(newUser);
          } else {
            this.sectorManagers.push(newUser);
          }
          this.resetUserForm();
          this.showToast('Utilisateur ajouté avec succès.', 'success');
        },
        error: (e) => {
          this.error = this.getRequestErrorMessage(e, 'Erreur lors de la creation de l’utilisateur.');
          this.showToast(this.error, 'error');
        },
      });
    }
  }

  toggleUserActive(userId: number) {
    this.http.post(`/api/auth/admin/users/${userId}/toggle/`, {}, this.httpOptions).subscribe({
      next: () => {
        let index = this.users.findIndex((user) => user.id === userId);
        if (index > -1) {
          this.users[index].is_active = !this.users[index].is_active;
          this.showToast(`Utilisateur ${this.users[index].is_active ? 'activé' : 'désactivé'} avec succès.`, 'success');
          return;
        }
        index = this.sectorManagers.findIndex((user) => user.id === userId);
        if (index > -1) {
          this.sectorManagers[index].is_active = !this.sectorManagers[index].is_active;
          this.showToast(`Responsable ${this.sectorManagers[index].is_active ? 'activé' : 'désactivé'} avec succès.`, 'success');
        }
      },
      error: (e) => {
        this.error = e.error?.detail || 'Erreur lors du changement de statut du responsable.';
        this.showToast(this.error, 'error');
      },
    });
  }

  deleteUser(userId: number) {
    if (!confirm('Supprimer cet utilisateur ?')) {
      return;
    }

    this.http.delete(`/api/auth/admin/users/${userId}/`, this.httpOptions).subscribe({
      next: () => {
        this.users = this.users.filter((user) => user.id !== userId);
        this.sectorManagers = this.sectorManagers.filter((user) => user.id !== userId);
        this.showToast('Utilisateur supprimé avec succès.', 'success');
      },
      error: (e) => {
        this.error = e.error?.detail || 'Erreur lors de la suppression de l’utilisateur.';
        this.showToast(this.error, 'error');
      },
    });
  }

  get filteredAdminUsers() {
    const search = this.userSearch.trim().toLowerCase();
    const users = [...this.sectorManagers, ...this.users]
      .filter((user) => this.adminUserFilter === 'all' || user.role === this.adminUserFilter)
      .sort((left, right) => {
        const lastNameCompare = (left.last_name || '').localeCompare(right.last_name || '');
        if (lastNameCompare !== 0) {
          return lastNameCompare;
        }
        return (left.first_name || '').localeCompare(right.first_name || '');
      });

    if (!search) {
      return users;
    }

    return users.filter((user) =>
      user.email.toLowerCase().includes(search) ||
      user.first_name.toLowerCase().includes(search) ||
      user.last_name.toLowerCase().includes(search) ||
      (user.branch__name || '').toLowerCase().includes(search) ||
      (user.branch__sector__name || '').toLowerCase().includes(search) ||
      (user.managed_sector__name || '').toLowerCase().includes(search)
    );
  }

  toggleAdminUserFilter(role: 'user' | 'sector_manager') {
    this.adminUserFilter = this.adminUserFilter === role ? 'all' : role;
  }

  get filteredSectorUsers() {
    const search = this.sectorUserSearch.trim().toLowerCase();
    if (!search) {
      return this.sectorUsers;
    }
    return this.sectorUsers.filter((user) =>
      user.first_name.toLowerCase().includes(search) ||
      user.last_name.toLowerCase().includes(search)
    );
  }

  get dashboardStats() {
    return {
      users: this.users.length,
      managers: this.sectorManagers.length,
      branches: this.branches.length,
      sectors: this.sectors.length,
      evaluations: this.evaluationOverview.session_count,
    };
  }

  resetEvaluationPagination() {
    this.evaluationPage = 1;
  }

  get evaluationPageCount() {
    return Math.max(1, Math.ceil(this.filteredEvaluations.length / this.evaluationPageSize));
  }

  get pagedFilteredEvaluations(): UserEvaluationSummary[] {
    const pageCount = this.evaluationPageCount;
    if (this.evaluationPage > pageCount) {
      this.evaluationPage = pageCount;
    }
    const start = (this.evaluationPage - 1) * this.evaluationPageSize;
    return this.filteredEvaluations.slice(start, start + this.evaluationPageSize);
  }

  get evaluationPageStart() {
    if (!this.filteredEvaluations.length) {
      return 0;
    }
    return (this.evaluationPage - 1) * this.evaluationPageSize + 1;
  }

  get evaluationPageEnd() {
    return Math.min(this.evaluationPage * this.evaluationPageSize, this.filteredEvaluations.length);
  }

  previousEvaluationPage() {
    if (this.evaluationPage > 1) {
      this.evaluationPage -= 1;
    }
  }

  nextEvaluationPage() {
    if (this.evaluationPage < this.evaluationPageCount) {
      this.evaluationPage += 1;
    }
  }

  cancelBranchForm() {
    this.resetBranchForm();
  }

  cancelSectorForm() {
    this.resetSectorForm();
  }

  cancelUserForm() {
    this.resetUserForm();
  }

  deleteBranch(branchId: number) {
    if (!confirm('Supprimer cette filiale ?')) {
      return;
    }
    this.http.delete(`/api/auth/admin/branches/${branchId}/`, this.httpOptions).subscribe({
      next: () => {
        this.branches = this.branches.filter((branch) => branch.id !== branchId);
      },
      error: (e) => this.error = e.error?.detail || 'Erreur lors de la suppression de la filiale.',
    });
  }

  openSectorChange(branch: { id: number; sectorId: number }) {
    this.sectorChangeBranchId = branch.id;
    this.sectorChangeSectorId = branch.sectorId;
  }

  cancelSectorChange() {
    this.sectorChangeBranchId = null;
    this.sectorChangeSectorId = null;
  }

  saveBranchSectorChange() {
    if (!this.sectorChangeBranchId || !this.sectorChangeSectorId) {
      this.error = 'Sélectionnez un secteur valide.';
      return;
    }

    this.http.post(`/api/auth/admin/branches/${this.sectorChangeBranchId}/change-sector/`, {
      sector_id: this.sectorChangeSectorId,
    }, this.httpOptions).subscribe({
      next: (result: any) => {
        const index = this.branches.findIndex((branch) => branch.id === this.sectorChangeBranchId);
        if (index > -1) {
          this.branches[index] = {
            ...this.branches[index],
            sector: result.sector_name || this.sectors.find((s) => s.id === this.sectorChangeSectorId)?.name || '',
            sectorId: result.sector_id || this.sectorChangeSectorId,
          };
        }
        this.sectorChangeBranchId = null;
        this.sectorChangeSectorId = null;
        this.error = '';
      },
      error: (e) => this.error = e.error?.detail || 'Erreur lors de la modification du secteur.',
    });
  }

  deleteSector(sectorId: number) {
    if (!confirm('Supprimer ce secteur ?')) {
      return;
    }
    this.http.delete(`/api/auth/admin/sectors/${sectorId}/`, this.httpOptions).subscribe({
      next: () => {
        this.sectors = this.sectors.filter((sector) => sector.id !== sectorId);
      },
      error: (e) => this.error = e.error?.detail || 'Erreur lors de la suppression du secteur.',
    });
  }

  get isAdminDashboard() {
    return this.connected && this.userRole === 'general_manager';
  }

  openRegister() {
    this.mode = 'register';
    if (this.role === 'general_manager') {
      this.role = 'user';
    }
    this.error = '';
    this.message = '';
    this.scrollToAccess();
  }

  toggleAuthMode() {
    this.mode = this.mode === 'login' ? 'register' : 'login';
    if (this.mode === 'register' && this.role === 'general_manager') {
      this.role = 'user';
    }
    this.error = '';
    this.message = '';
    this.scrollToAccess();
  }

  private scrollToAccess() {
    setTimeout(() => {
      document.getElementById('access')?.scrollIntoView({
        behavior: 'smooth',
        block: 'start',
      });
    }, 50);
  }

  get groupedEvaluations() {
    const groups = new Map<string, EvaluationRow[]>();
    for (const ev of this.evaluations) {
      const axe = String(ev.axe_evaluation || '').trim() || 'Sans axe';
      if (!groups.has(axe)) {
        groups.set(axe, []);
      }
      groups.get(axe)!.push(ev);
    }
    return Array.from(groups.entries()).map(([axe, rows]) => ({
      axe,
      rows,
    }));
  }

  get filteredUserEvaluations(): UserEvaluationSummary[] {
    const search = this.userEvaluationSearch.trim().toLowerCase();
    if (!search) {
      return this.userEvaluationList;
    }
    return this.userEvaluationList.filter((ev) =>
      ev.periode.toLowerCase().includes(search)
    );
  }

  get userEvaluationStats() {
    const evs = this.userEvaluationList;
    if (!evs.length) {
      return { total: 0, avgConformite: 0, bestNote: null, minNote: null };
    }
    const bestNotes: number[] = [];
    const minNotes: number[] = [];
    const conformites: number[] = [];
    for (const ev of evs) {
      const bestNoteValue = parseFloat(String(ev.max_note ?? ev.note_moyenne ?? '').replace(',', '.'));
      const minNoteValue = parseFloat(String(ev.min_note ?? ev.note_moyenne ?? '').replace(',', '.'));
      const conf = parseFloat(String(ev.conformite_globale || '').replace(',', '.'));
      if (!Number.isNaN(bestNoteValue)) bestNotes.push(bestNoteValue);
      if (!Number.isNaN(minNoteValue)) minNotes.push(minNoteValue);
      if (!Number.isNaN(conf)) conformites.push(conf);
    }
    const bestNote = bestNotes.length ? Math.max(...bestNotes) : null;
    const minNote = minNotes.length ? Math.min(...minNotes) : null;
    const avgConformite = conformites.length ? conformites.reduce((a, b) => a + b, 0) / conformites.length : 0;
    return {
      total: evs.length,
      avgConformite: Math.round(avgConformite * 100) / 100,
      bestNote,
      minNote,
    };
  }

  getConformiteNumber(ev: UserEvaluationSummary): number {
    return parseFloat(String(ev.conformite_globale || '').replace(',', '.'));
  }

  get groupedSelectedEvaluations(): Array<{ axis: string; rows: EvaluationRow[] }> {
    const map = new Map<string, EvaluationRow[]>();
    for (const row of this.selectedEvaluation) {
      const key = row.axe_evaluation || 'Sans axe';
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(row);
    }
    return Array.from(map.entries()).map(([axis, rows]) => ({ axis, rows }));
  }

  get selectedEvaluationSummary(): { total: string; max: string; conformite: string } {
    const rows = this.selectedEvaluation;
    if (!rows.length) return { total: '—', max: '—', conformite: '0.0' };
    let totalWeighted = 0;
    let totalMax = 0;
    for (const row of rows) {
      try {
        const n = parseFloat(String(row.note || '0').replace(',', '.'));
        const p = parseFloat(String(row.ponderation || '0').replace(',', '.'));
        totalWeighted += (isNaN(n) ? 0 : n) * (isNaN(p) ? 0 : p);
        totalMax += 20 * (isNaN(p) ? 0 : p);
      } catch {
        /* ignore */
      }
    }
    const conf = totalMax > 0 ? ((totalWeighted / totalMax) * 100).toFixed(1) : '0.0';
    return {
      total: totalWeighted.toFixed(0),
      max: totalMax.toFixed(0),
      conformite: conf,
    };
  }

  get checklistMaxPossible(): number {
    let total = 0;
    ISO_17025_CHECKLIST.forEach((axis) => {
      axis.criteria.forEach((c) => {
        total += 20 * c.weight;
      });
    });
    return total;
  }

  get checklistTotalCriteria(): number {
    return ISO_17025_CHECKLIST.reduce((sum, a) => sum + a.criteria.length, 0);
  }

  get checklistTotalWeight(): number {
    return ISO_17025_CHECKLIST.reduce(
      (sum, a) => sum + a.criteria.reduce((s, c) => s + c.weight, 0),
      0
    );
  }

  get checklistGlobalScore(): number | null {
    let totalWeighted = 0;
    let totalWeight = 0;
    ISO_17025_CHECKLIST.forEach((axis, axIdx) => {
      axis.criteria.forEach((c, cIdx) => {
        const note = this.getChecklistNote(axIdx, cIdx);
        if (note !== null && c.weight > 0) {
          totalWeighted += note * c.weight;
          totalWeight += c.weight;
        } else if (c.weight > 0) {
          totalWeight += c.weight;
        }
      });
    });
    if (totalWeight === 0) return null;
    return Math.round((totalWeighted / totalWeight) * 100) / 100;
  }

  getChecklistNote(axIdx: number, cIdx: number): number | null {
    const row = this.checklistFormData[axIdx]?.[cIdx];
    if (!row) return null;
    const v = parseFloat(row.note);
    if (isNaN(v) || v < 0 || v > 20) return null;
    return v;
  }

  getChecklistObservation(axIdx: number, cIdx: number): string {
    return this.checklistFormData[axIdx]?.[cIdx]?.observation || '';
  }

  getChecklistAxisScore(axIdx: number): number | null {
    const axis = ISO_17025_CHECKLIST[axIdx];
    if (!axis) return null;
    let totalWeighted = 0;
    let totalWeight = 0;
    axis.criteria.forEach((c, cIdx) => {
      const note = this.getChecklistNote(axIdx, cIdx);
      if (note !== null && c.weight > 0) {
        totalWeighted += note * c.weight;
        totalWeight += c.weight;
      } else if (c.weight > 0) {
        totalWeight += c.weight;
      }
    });
    if (totalWeight === 0) return null;
    return Math.round((totalWeighted / totalWeight) * 100) / 100;
  }

  getChecklistAxisWeight(axIdx: number): number {
    const axis = ISO_17025_CHECKLIST[axIdx];
    if (!axis) return 0;
    return axis.criteria.reduce((s, c) => s + c.weight, 0);
  }

  getChecklistFilledCount(): number {
    let count = 0;
    ISO_17025_CHECKLIST.forEach((axis, axIdx) => {
      axis.criteria.forEach((c, cIdx) => {
        if (this.getChecklistNote(axIdx, cIdx) !== null) {
          count++;
        }
      });
    });
    return count;
  }

  getChecklistMissingCount(): number {
    return this.checklistTotalCriteria - this.getChecklistFilledCount();
  }

  loadUserEvaluationList() {
    if (this.userEvaluationListLoading) {
      return;
    }

    const cachedUserEvaluations = this.readSessionCache<UserEvaluationSummary[]>(this.userEvaluationCacheKey);
    if (cachedUserEvaluations?.length && !this.userEvaluationListLoaded) {
      this.applyUserEvaluationList(cachedUserEvaluations);
    }

    this.userEvaluationListLoading = true;
    this.evaluationError = '';
    this.http.get<{ evaluations: any[] }>(this.withNoCache('/api/auth/user/evaluations-summary/'), this.httpOptions).pipe(
      timeout(this.requestTimeoutMs),
      finalize(() => {
        this.userEvaluationListLoading = false;
      })
    ).subscribe({
      next: (r) => {
        const evaluations = (r.evaluations || []).map((ev) => this.mapEvaluationSummary(ev));
        this.applyUserEvaluationList(evaluations);
        this.writeSessionCache(this.userEvaluationCacheKey, evaluations);
      },
      error: (e) => {
        this.evaluationError = this.getRequestErrorMessage(e, 'Impossible de charger la liste des évaluations.');
        this.showToast(this.evaluationError, 'error');
      },
    });
  }

  viewEvaluationDetail(ev: UserEvaluationSummary) {
    this.evaluationError = '';
    this.evaluationSuccess = '';
    this.evaluationSaveMessage = '';
    this.evaluationSaveError = '';
    this.mlPredictionError = '';
    this.selectedEvaluationPrediction = null;
    const params = new URLSearchParams();
    if (ev.id) {
      params.set('id', String(ev.id));
    }
    if (ev['mois']) params.set('mois', String(ev['mois']));
    if (ev['annee']) params.set('annee', String(ev['annee']));
    if (ev['date_id']) params.set('date_id', String(ev['date_id']));
    if (ev['filiale_id']) params.set('filiale_id', String(ev['filiale_id']));
    else if (ev.filiale_name && ev.filiale_name !== '—') params.set('filiale_name', ev.filiale_name);
    if (ev['laboratoire_id']) params.set('laboratoire_id', String(ev['laboratoire_id']));
    if (ev['user_id']) params.set('user_id', String(ev['user_id']));
    const detailEndpoint = this.userRole === 'user' ? '/api/auth/user/evaluations-session/' : '/api/auth/evaluations-session/';
    this.http.get<{ evaluations: any[] }>(this.withNoCache(`${detailEndpoint}?${params.toString()}`), this.httpOptions).subscribe({
      next: (r) => {
        const enableEditMode = this.pendingDetailEditMode;
        const rows: EvaluationRow[] = (r.evaluations || []).map((data) => ({
          id: Number(data.id || 0),
          line_pk: data.line_pk || null,
          month: data.mois || data.month || '',
          year: data.annee || data.year || '',
          trimestre: data.trimestre || '',
          filiale_id: data.filiale_id || null,
          filiale: data.filiale_name || data.filiale || '',
          filiale_name: data.filiale_name || data.filiale || '',
          secteur_name: data.secteur_name || '',
          manager_name: data.manager_name || '',
          code: String(data.code || data.filiale_code || ''),
          laboratoire: data.laboratoire_name || data.laboratoire || '',
          laboratoire_name: data.laboratoire_name || data.laboratoire || '',
          axe_evaluation: data.axe_evaluation || '',
          criteres: data.criteres || '',
          note: data.note || '',
          ponderation: data.ponderation || '',
          moy_ponderation: data.moy_ponderation || '',
          tx_conformite: data.tx_conformite || '',
          observations: data.observations || '',
          user_id: data.user_id || null,
          user_name: data.user_name || '',
          moyenne_axe: data.moyenne_axe ?? null,
          conformite_axe: data.conformite_axe ?? null,
          editing: enableEditMode,
          isSaving: false,
          isDeleting: false,
        }));
        this.selectedEvaluation = rows;
        this.selectedEvaluationTitle = `Détail — ${ev.user_name || 'Utilisateur'} — ${ev.periode} — ${ev.filiale_name}`;
        this.isEvaluationDetailMode = true;
        this.pendingDetailEditMode = false;
        setTimeout(() => window.scrollTo({ top: 0, behavior: 'smooth' }), 0);
        if (this.pendingDetailPdfExport) {
          this.pendingDetailPdfExport = false;
          setTimeout(() => this.exportEvaluationDetailPdf(), 0);
        }
      },
      error: (e) => {
        this.pendingDetailPdfExport = false;
        this.pendingDetailEditMode = false;
        this.evaluationError = e.error?.detail || 'Impossible de charger le détail de l\'évaluation.';
        this.showToast(this.evaluationError, 'error');
      },
    });
  }

  viewEvaluationDetailAndExportPdf(ev: UserEvaluationSummary) {
    this.pendingDetailPdfExport = true;
    this.viewEvaluationDetail(ev);
  }

  editEvaluationSession(ev: UserEvaluationSummary) {
    this.pendingDetailEditMode = true;
    this.viewEvaluationDetail(ev);
  }

  backToList() {
    this.isEvaluationDetailMode = false;
    this.isEvaluationFormMode = false;
    this.selectedEvaluation = [];
    this.selectedEvaluationTitle = '';
    this.checklistFormData = [];
    this.checklistPrediction = null;
    this.selectedEvaluationPrediction = null;
    this.mlPredictionError = '';
    this.pendingDetailPdfExport = false;
    this.pendingDetailEditMode = false;
    this.evaluationSaveMessage = '';
    this.evaluationSaveError = '';
    if (this.userRole === 'user' && this.userEvaluationListStale) {
      this.loadUserEvaluationList();
    } else if (this.userRole !== 'user' && this.evaluationSummariesStale) {
      this.loadEvaluations(true);
    }
  }

  get selectedEvaluationMeta(): { filiale: string; secteur: string; user: string; manager: string } {
    const firstRow = this.selectedEvaluation[0];
    if (!firstRow) {
      return { filiale: '—', secteur: '—', user: '—', manager: '—' };
    }

    const resolvedSectorName = this.resolveSectorNameFromFiliale(firstRow);

    return {
      filiale: firstRow.filiale_name || firstRow.filiale || '—',
      secteur: resolvedSectorName,
      user: firstRow.user_name || '—',
      manager: firstRow.manager_name || '—',
    };
  }

  get userHomeImageSrc(): string {
    const sector = (this.userSectorName || '').trim().toLocaleLowerCase('fr');
    if (sector.includes('agro')) {
      return '/agro.jpg';
    }
    if (sector.includes('aliment')) {
      return '/aliment.png';
    }
    return '/avicole.png';
  }

  get userHomeImageAlt(): string {
    const sector = this.userSectorName || 'utilisateur';
    return `Illustration du secteur ${sector}`;
  }

  private getPdfLogoSrc(): string {
    if (typeof window === 'undefined') {
      return '/logo.png';
    }
    return `${window.location.origin}/logo.png`;
  }

  private buildPdfDocument(title: string, subtitle: string, content: string): string {
    const generatedAt = new Date().toLocaleString('fr-FR');
    return `
      <html>
        <head>
          <title>${title}</title>
          <style>
            body { font-family: 'Segoe UI', Roboto, Arial, sans-serif; margin: 24px; color: #18314f; }
            .pdf-brand { display: flex; align-items: center; justify-content: space-between; gap: 16px; border-bottom: 2px solid #cadaff; padding-bottom: 14px; margin-bottom: 18px; }
            .pdf-brand-main { display: flex; align-items: center; gap: 14px; }
            .pdf-brand img { width: 56px; height: 56px; object-fit: contain; }
            .pdf-company { font-size: 22px; font-weight: 800; color: #24489f; margin: 0; }
            .pdf-subtitle { font-size: 12px; color: #5f7394; margin-top: 3px; }
            .pdf-generated { font-size: 11px; color: #7083a2; text-align: right; }
            h1 { font-size: 20px; margin: 0 0 6px; color: #24489f; }
            h2 { font-size: 15px; margin: 12px 0 10px; color: #345fcb; }
            p { margin: 0 0 12px; color: #555; font-size: 12px; }
            .meta { display: flex; gap: 14px; margin-bottom: 14px; flex-wrap: wrap; }
            .meta-item { background: #eef4ff; padding: 6px 10px; border-radius: 6px; font-size: 12px; }
            .meta-item span { font-weight: 600; }
            .summary { float: right; background: #eef4ff; border: 1px solid #cadaff; border-radius: 8px; padding: 10px 14px; text-align: right; }
            .summary .total { font-size: 20px; font-weight: 700; color: #345fcb; }
            .summary .conf { font-size: 14px; color: #345fcb; font-weight: 600; }
            table { width: 100%; border-collapse: collapse; margin-top: 12px; clear: both; }
            th, td { border: 1px solid #444; padding: 6px 8px; text-align: left; vertical-align: top; font-size: 11px; }
            th { background: #eef4ff; color: #24489f; font-weight: 700; }
            tr:nth-child(even) td { background: #f7faff; }
            .pdf-signature { margin-top: 28px; display: flex; justify-content: flex-end; }
            .pdf-signature-card { width: 250px; text-align: center; }
            .pdf-signature-title { font-size: 12px; font-weight: 700; color: #345fcb; margin-bottom: 34px; }
            .pdf-signature-line { border-bottom: 1px solid #8b9cc0; margin-bottom: 8px; }
            .pdf-signature-note { font-size: 11px; color: #62779a; }
            .pdf-footer { margin-top: 18px; text-align: center; font-size: 10px; color: #7c8fb0; }
          </style>
        </head>
        <body>
          <header class="pdf-brand">
            <div class="pdf-brand-main">
              <img src="${this.getPdfLogoSrc()}" alt="Logo Poulina Group Holding">
              <div>
                <div class="pdf-company">Poulina Group Holding</div>
                <div class="pdf-subtitle">${subtitle}</div>
              </div>
            </div>
            <div class="pdf-generated">Édité le<br>${generatedAt}</div>
          </header>
          ${content}
          <section class="pdf-signature">
            <div class="pdf-signature-card">
              <div class="pdf-signature-title">Signature</div>
              <div class="pdf-signature-line"></div>
              <div class="pdf-signature-note">Cachet et signature autorisée</div>
            </div>
          </section>
          <div class="pdf-footer">Document officiel - Poulina Group Holding</div>
        </body>
      </html>
    `;
  }

  private resolveSectorNameFromFiliale(row: EvaluationRow): string {
    if (row.secteur_name && row.secteur_name.trim()) {
      return row.secteur_name;
    }

    const branchById = row.filiale_id
      ? this.branches.find((branch) => branch.id === row.filiale_id)
      : null;
    if (branchById?.sector) {
      return branchById.sector;
    }

    const rowFilialeName = (row.filiale_name || row.filiale || '').trim().toLocaleLowerCase('fr');
    if (rowFilialeName) {
      const branchByName = this.branches.find(
        (branch) => branch.name.trim().toLocaleLowerCase('fr') === rowFilialeName
      );
      if (branchByName?.sector) {
        return branchByName.sector;
      }
    }

    return '—';
  }

  exportUserEvaluationPdf() {
    if (!this.userEvaluationList.length) {
      return;
    }
    const tableRows = this.userEvaluationList.map((ev) => {
      const note = ev.note_moyenne !== undefined && ev.note_moyenne !== '—' ? ev.note_moyenne : '—';
      const conf = ev.conformite_globale !== undefined && ev.conformite_globale !== '—' ? `${ev.conformite_globale}%` : '—';
      return `
        <tr>
          <td>${ev.periode}</td>
          <td>${ev.filiale_name}</td>
          <td>${ev.secteur_name}</td>
          <td>${ev.user_name}</td>
          <td>${note}</td>
          <td>${conf}</td>
        </tr>
      `;
    }).join('');

    const printWindow = window.open('', '_blank');
    if (!printWindow) {
      this.evaluationError = 'Impossible d’ouvrir la fenêtre d’export PDF.';
      return;
    }
    printWindow.document.write(this.buildPdfDocument(
      'Mes évaluations',
      'Synthèse des évaluations personnelles',
      `
        <h1>Mes évaluations</h1>
        <p>Utilisateur : ${this.userFirstName || ''} ${this.userLastName || ''}</p>
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Filiale</th>
              <th>Secteur</th>
              <th>Utilisateur</th>
              <th>Note moyenne</th>
              <th>Conformité globale</th>
            </tr>
          </thead>
          <tbody>${tableRows}</tbody>
        </table>
      `
    ));
    printWindow.document.close();
    printWindow.focus();
    printWindow.print();
  }

  addEvaluationForUser() {
    this.checklistFormData = ISO_17025_CHECKLIST.map((axis) =>
      axis.criteria.map(() => ({ note: '', observation: '' }))
    );
    const months = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin', 'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre'];
    const now = new Date();
    this.checklistMonth = months[now.getMonth()] || 'Janvier';
    this.checklistYear = String(now.getFullYear());
    this.checklistLaboratoire = this.userBranchName || '';
    this.checklistAuditeur = this.userFirstName && this.userLastName ? `${this.userFirstName} ${this.userLastName}` : '';
    this.isEvaluationFormMode = true;
    this.isEvaluationDetailMode = false;
    this.selectedEvaluation = [];
    this.selectedEvaluationTitle = 'Nouvelle évaluation — Checklist Contrôle Laboratoire';
    this.evaluationSaveMessage = '';
    this.evaluationSaveError = '';
    this.mlPredictionError = '';
    this.checklistPrediction = null;
    this.selectedEvaluationPrediction = null;
  }

  cancelChecklistForm() {
    this.isEvaluationFormMode = false;
    this.checklistFormData = [];
    this.evaluationSaveMessage = '';
    this.evaluationSaveError = '';
    this.mlPredictionError = '';
    this.checklistPrediction = null;
  }

  resetChecklistForm() {
    this.checklistFormData = ISO_17025_CHECKLIST.map((axis) =>
      axis.criteria.map(() => ({ note: '', observation: '' }))
    );
    this.evaluationSaveMessage = '';
    this.evaluationSaveError = '';
    this.mlPredictionError = '';
    this.checklistPrediction = null;
  }

  saveChecklistForm(afterSaveCallback?: () => void) {
    this.evaluationSaveError = '';
    this.evaluationSaveMessage = '';

    const missing = this.getChecklistMissingCount();
    if (missing > 0) {
      this.evaluationSaveError = `Il reste ${missing} critère(s) sans note. Veuillez saisir une note entre 0 et 20 pour chaque critère.`;
      return;
    }

    const payload: any[] = [];
    ISO_17025_CHECKLIST.forEach((axis, axIdx) => {
      axis.criteria.forEach((c, cIdx) => {
        const note = this.getChecklistNote(axIdx, cIdx);
        const obs = this.getChecklistObservation(axIdx, cIdx);
        const code = String(this.userBranchCode || '');
        const filialeName = this.userBranchName || '';
        const month = this.checklistMonth || '';
        const year = String(this.checklistYear || '');
        const laboName = this.checklistLaboratoire || this.userBranchName || '';
        payload.push({
          month,
          year,
          filiale: filialeName,
          code,
          laboratoire: laboName,
          axe_evaluation: axis.title,
          criteres: c.text,
          note: note !== null ? String(note) : '',
          ponderation: String(c.weight),
          observations: obs,
        });
      });
    });

    this.http.post<{ saved: number; created: number; updated: number; errors?: string[] }>(
      '/api/auth/user/evaluations/',
      { evaluations: payload },
      this.httpOptions
    ).subscribe({
      next: (response) => {
        if (response.saved > 0) {
          this.evaluationSaveMessage = `${response.saved} évaluation(s) enregistrée(s) avec succès (${response.created} créées, ${response.updated} mises à jour).`;
          this.markEvaluationListsStale();
          this.showToast(this.evaluationSaveMessage, 'success');
          if (afterSaveCallback) {
            setTimeout(() => afterSaveCallback(), 400);
          } else {
            this.isEvaluationFormMode = false;
            this.checklistFormData = [];
            setTimeout(() => this.loadUserEvaluationList(), 0);
          }
        } else {
          this.evaluationSaveError = 'Aucune évaluation n’a été enregistrée.';
          this.showToast(this.evaluationSaveError, 'info');
        }
        if (response.errors && response.errors.length) {
          this.evaluationSaveError = (this.evaluationSaveError ? this.evaluationSaveError + ' — ' : '') + response.errors.join(' ');
          this.showToast(this.evaluationSaveError, 'error');
        }
      },
      error: (e) => {
        this.evaluationSaveError = e.error?.errors?.join(' ') || e.error?.detail || 'Erreur lors de l’enregistrement.';
        this.showToast(this.evaluationSaveError, 'error');
      },
    });
  }

  saveChecklistFormAndPdf() {
    this.saveChecklistForm(() => {
      this.exportChecklistFormPdf();
      this.isEvaluationFormMode = false;
      this.checklistFormData = [];
      setTimeout(() => this.loadUserEvaluationList(), 0);
    });
  }

  exportChecklistFormPdf() {
    const total = this.checklistGlobalScore;
    const maxPossible = this.checklistMaxPossible || 200;
    const conform = maxPossible > 0 ? ((total || 0) / (maxPossible || 200)) * 100 : 0;
    let htmlAxes = '';
    ISO_17025_CHECKLIST.forEach((axe, axIdx) => {
      axe.criteria.forEach((c, cIdx) => {
        const note = this.getChecklistNote(axIdx, cIdx) ?? '';
        const obs = this.getChecklistObservation(axIdx, cIdx) || '';
        htmlAxes += `
          <tr>
            <td>${cIdx === 0 ? axe.title : ''}</td>
            <td>${c.text}</td>
            <td style="text-align:center">${note !== '' ? note + '/20' : ''}</td>
            <td style="text-align:center">${c.weight}</td>
            <td>${obs}</td>
          </tr>`;
      });
    });
    const printWindow = window.open('', '_blank');
    if (!printWindow) {
      this.evaluationError = 'Impossible d’ouvrir la fenêtre d’export PDF.';
      return;
    }
    printWindow.document.write(this.buildPdfDocument(
      'Évaluation - Checklist Contrôle Laboratoire',
      'Formulaire de saisie des notes des axes',
      `
        <div class="summary">
          <div class="total">${(total || 0).toFixed(0)} / ${maxPossible}</div>
          <div class="conf">Conformité ${conform.toFixed(1)} %</div>
        </div>
        <h1>3. FORMULAIRE DE SAISIE DES NOTES DES AXES</h1>
        <h2>Nouvelle évaluation — Checklist Contrôle Laboratoire</h2>
        <div class="meta">
          <div class="meta-item"><span>Mois :</span> ${this.checklistMonth || ''}</div>
          <div class="meta-item"><span>Année :</span> ${this.checklistYear || ''}</div>
          <div class="meta-item"><span>Laboratoire :</span> ${this.checklistLaboratoire || this.userBranchName || ''}</div>
          <div class="meta-item"><span>Auditeur :</span> ${this.checklistAuditeur || this.userFirstName + ' ' + this.userLastName || ''}</div>
        </div>
        <table>
          <thead>
            <tr>
              <th>Axe d'évaluation</th>
              <th>Critères d'évaluation</th>
              <th>Note /20</th>
              <th>Pondération</th>
              <th>Observation</th>
            </tr>
          </thead>
          <tbody>${htmlAxes}</tbody>
        </table>
      `
    ));
    printWindow.document.close();
    printWindow.focus();
    setTimeout(() => printWindow.print(), 300);
  }

  exportEvaluationDetailPdf() {
    if (!this.selectedEvaluation.length) return;
    const sessionsRows = this.selectedEvaluation;
    const period = `${sessionsRows[0].month || ''} ${sessionsRows[0].year || ''}`.trim();
    const filiale = sessionsRows[0].filiale_name || sessionsRows[0].filiale || '';
    const laboratoire = sessionsRows[0].laboratoire_name || sessionsRows[0].laboratoire || '';
    const user = sessionsRows[0].user_name || '';
    let totalWeighted = 0;
    let totalMax = 0;
    sessionsRows.forEach(row => {
      try {
        const n = parseFloat(row.note || '0');
        const p = parseFloat(row.ponderation || '0');
        totalWeighted += n * p;
        totalMax += 20 * p;
      } catch { /* ignore */ }
    });
    const conform = totalMax > 0 ? (totalWeighted / totalMax) * 100 : 0;
    const grouped: Record<string, EvaluationRow[]> = {};
    sessionsRows.forEach(r => {
      const key = r.axe_evaluation || 'Sans axe';
      if (!grouped[key]) grouped[key] = [];
      grouped[key].push(r);
    });
    let htmlRows = '';
    Object.keys(grouped).forEach(axeName => {
      grouped[axeName].forEach((row, i) => {
        htmlRows += `
          <tr>
            <td>${i === 0 ? axeName : ''}</td>
            <td>${row.criteres || ''}</td>
            <td style="text-align:center">${row.note ? row.note + '/20' : ''}</td>
            <td style="text-align:center">${row.ponderation || ''}</td>
            <td>${row.observations || ''}</td>
          </tr>`;
      });
    });
    const printWindow = window.open('', '_blank');
    if (!printWindow) {
      this.evaluationError = 'Impossible d’ouvrir la fenêtre d’export PDF.';
      return;
    }
    printWindow.document.write(this.buildPdfDocument(
      `Évaluation - ${period} ${filiale}`.trim(),
      'Détail d’une évaluation laboratoire',
      `
        <div class="summary">
          <div class="total">${totalWeighted.toFixed(0)} / ${totalMax.toFixed(0)}</div>
          <div class="conf">Conformité ${conform.toFixed(1)} %</div>
        </div>
        <h1>Évaluation — Checklist Contrôle Laboratoire</h1>
        <div class="meta">
          <div class="meta-item"><span>Période :</span> ${period}</div>
          <div class="meta-item"><span>Filiale :</span> ${filiale}</div>
          <div class="meta-item"><span>Laboratoire :</span> ${laboratoire}</div>
          <div class="meta-item"><span>Auditeur :</span> ${user}</div>
        </div>
        <table>
          <thead>
            <tr>
              <th>Axe d'évaluation</th>
              <th>Critères d'évaluation</th>
              <th>Note /20</th>
              <th>Pondération</th>
              <th>Observation</th>
            </tr>
          </thead>
          <tbody>${htmlRows}</tbody>
        </table>
      `
    ));
    printWindow.document.close();
    printWindow.focus();
    setTimeout(() => printWindow.print(), 300);
  }

  exportChecklistConsole() {
    const data: any[] = [];
    ISO_17025_CHECKLIST.forEach((axis, axIdx) => {
      axis.criteria.forEach((c, cIdx) => {
        const note = this.getChecklistNote(axIdx, cIdx);
        const obs = this.getChecklistObservation(axIdx, cIdx);
        data.push({
          axe: axis.title,
          critere: c.text,
          note: note,
          ponderation: c.weight,
          observation: obs,
        });
      });
    });
    const globalScore = this.checklistGlobalScore;
    const output = {
      date: new Date().toLocaleString(),
      globalScore: globalScore !== null ? globalScore : null,
      details: data,
    };
    console.log('📤 EXPORT ÉVALUATION ISO 17025', JSON.stringify(output, null, 2));
  }

  editEvaluationRowUser(evaluation: EvaluationRow) {
    evaluation.editing = true;
  }

  deleteEvaluationRowUser(evaluation: EvaluationRow) {
    if (!evaluation.line_pk) {
      const index = this.selectedEvaluation.indexOf(evaluation);
      if (index > -1) {
        this.selectedEvaluation.splice(index, 1);
      }
      if (this.selectedEvaluation.length === 0) {
        this.backToList();
      }
      return;
    }
    if (!confirm('Supprimer cette évaluation ?')) {
      return;
    }
    const detailEndpoint = '/api/auth/user/evaluations/' + evaluation.line_pk + '/';
    this.http.delete(detailEndpoint, this.httpOptions).subscribe({
      next: () => {
        const index = this.selectedEvaluation.indexOf(evaluation);
        if (index > -1) {
          this.selectedEvaluation.splice(index, 1);
        }
        this.evaluationSaveMessage = 'Évaluation supprimée.';
        this.loadUserEvaluationList();
        if (this.selectedEvaluation.length === 0) {
          this.backToList();
        }
      },
      error: (e) => {
        this.evaluationSaveError = e.error?.detail || 'Erreur lors de la suppression.';
      },
    });
  }

  private scrollToTop(behavior: ScrollBehavior = 'smooth') {
    setTimeout(() => {
      window.scrollTo({ top: 0, behavior });
    }, 50);
  }

  private initScrollReveal() {
    const elements = document.querySelectorAll<HTMLElement>('.reveal-on-scroll');

    if (!elements.length) {
      return;
    }

    this.observer?.disconnect();

    if (!('IntersectionObserver' in window)) {
      elements.forEach((element) => element.classList.add('is-visible'));
      return;
    }

    this.observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-visible');
            this.observer?.unobserve(entry.target);
          }
        });
      },
      {
        threshold: 0.18,
        rootMargin: '0px 0px -10% 0px',
      }
    );

    elements.forEach((element) => this.observer?.observe(element));
  }
}
