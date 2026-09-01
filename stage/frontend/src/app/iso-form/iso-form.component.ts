import { Component, EventEmitter, Output, OnInit, OnDestroy } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';

type IsoCriterionRaw = {
  text: string;
  weight: number;
};

type IsoCriterion = {
  text: string;
  weight: number;
  note: string;
  obs: string;
};

type IsoAxe = {
  id: number;
  title: string;
  criteria: IsoCriterion[];
  collapsed?: boolean;
};

@Component({
  selector: 'app-iso-form',
  standalone: true,
  imports: [FormsModule, CommonModule],
  templateUrl: './iso-form.component.html',
  styleUrl: './iso-form.component.css'
})
export class IsoFormComponent implements OnInit {
  @Output() saved = new EventEmitter<void>();
  @Output() cancelled = new EventEmitter<void>();

  axesData: IsoAxe[] = [];
  private rawAxesData: Array<{ id: number; title: string; criteria: IsoCriterionRaw[] }> = [
    {
      id: 1,
      title: 'Infrastructure et environnement de travail',
      criteria: [
        { text: "Organisation et séparation adéquate des zones de travail afin d'éviter toute contamination, confusion ou altération des résultats (marche en avant, présence d'affichage signalétique)", weight: 2 },
        { text: 'Conditions environnementales maîtrisées et surveillées : température, humidité, propreté, ventilation, éclairage, sécurité', weight: 2 },
        { text: 'Contrôle des accès aux zones sensibles et sécurité du laboratoire', weight: 2 },
        { text: "Disponibilité des consignes de sécurité, plans d'urgence et signalétique", weight: 2 },
      ]
    },
    {
      id: 2,
      title: 'Management documentaire et maîtrise des méthodes',
      criteria: [
        { text: "Disponibilité des méthodes d'analyse validées et à jour", weight: 3 },
        { text: 'Maîtrise des documents et enregistrements (version, archivage, diffusion)', weight: 3 },
        { text: 'Disponibilité des plans de contrôle et instructions de travail', weight: 2 },
        { text: "Application des plans d'analyse et respect de plan de contrôle", weight: 2 },
        { text: 'Gestion des modifications documentaires et approbation des documents', weight: 2 },
      ]
    },
    {
      id: 3,
      title: 'Échantillonnage, traçabilité et intégrité des données',
      criteria: [
        { text: "Procédures d'échantillonnage maîtrisées et documentées", weight: 3 },
        { text: 'Identification traçabilité complète des échantillons, des analyses', weight: 3 },
        { text: 'Conditions de transport, stockage et conservation maîtrisées', weight: 2 },
        { text: "Traçabilité et conservations des analyses laboratoire : fiche paillage, fiche intervention sur instrument, vérification interne…", weight: 3 },
      ]
    },
    {
      id: 4,
      title: 'Équipements et métrologie',
      criteria: [
        { text: 'Inventaire des équipements / réactifs disponible et à jour', weight: 2 },
        { text: 'Maintenance préventive et corrective documentée : CTA, hotte chimique/efflux laminaire', weight: 2 },
        { text: 'Étalonnage et vérification métrologique réalisés selon planning', weight: 4 },
        { text: 'Statut métrologique identifiable sur chaque équipement', weight: 2 },
        { text: 'Gestion des pannes et impact sur la validité / fiabilité des résultats évalué', weight: 2 },
      ]
    },
    {
      id: 5,
      title: 'Compétence du personnel',
      criteria: [
        { text: 'Définition des fonctions et responsabilités du personnel laboratoire', weight: 2 },
        { text: 'Qualification et habilitation du personnel documentées : Disponibilité des compétences, polyvalence, niveau de formation', weight: 3 },
        { text: "Évaluation des compétences techniques (aptitude du personnel laboratoire aux analyses réalisées : audit protocole)", weight: 5 },
        { text: 'Évaluation périodique des compétences techniques', weight: 2 },
        { text: "Plan de formation et suivi des compétences disponible (Sensibilisation aux exigences qualité et impartialité)", weight: 2 },
      ]
    },
    {
      id: 6,
      title: 'Assurance qualité des résultats',
      criteria: [
        { text: 'Respect de plan de CQ physicochimique et microbiologique : Mise en œuvre des contrôles qualité internes (CQI)', weight: 4 },
        { text: 'Comparaisons des résultats avec des résultats laboratoires accrédités (validation des résultats de contrôle)', weight: 3 },
        { text: 'Surveillance des tendances et exploitation statistique des résultats', weight: 2 },
        { text: 'Disponibilité et mise à jour des instructions laboratoire, plan de contrôle', weight: 2 },
      ]
    },
    {
      id: 7,
      title: 'Exploitation laboratoire et Gestion des réactifs, consommables et stocks',
      criteria: [
        { text: 'Identification et conformité des réactifs chimiques', weight: 2 },
        { text: 'Conditions de stockage adaptées et surveillées : bonne gestion des réactifs dangereux et application des normes de BP de stockage dans un laboratoire de CQ', weight: 2 },
        { text: 'Gestion des dates de péremption et FEFO/FIFO', weight: 2 },
        { text: 'Gestion des stocks assuré systématiquement : absence de réactifs avec DLC perméables', weight: 1 },
      ]
    },
    {
      id: 8,
      title: 'Sécurité et gestion des déchets',
      criteria: [
        { text: 'Respect des règles HSE et port des EPI', weight: 2 },
        { text: 'Gestion des déchets chimiques et biologiques conforme', weight: 2 },
        { text: 'Disponibilité des FDS et gestion des produits dangereux', weight: 2 },
        { text: "Procédures de gestion des incidents et situations d'urgence", weight: 2 },
      ]
    },
    {
      id: 9,
      title: 'Prestations externes et sous-traitance',
      criteria: [
        { text: 'Évaluation et suivi des laboratoires sous-traitants', weight: 3 },
        { text: 'Vérification des accréditations et compétences des prestataires', weight: 3 },
        { text: 'Maîtrise du transport des échantillons externalisés', weight: 2 },
      ]
    },
    {
      id: 10,
      title: 'Gestion des non-conformités et amélioration',
      criteria: [
        { text: "Détection et traitement des non-conformités (plan d'action)", weight: 2 },
        { text: "Mise en œuvre des actions correctives et suivi d'efficacité", weight: 1 },
      ]
    },
    {
      id: 11,
      title: 'Axe documentaire / QUALIPRO',
      criteria: [
        { text: "Exploitation du système, suivi des indicateurs, reporting, gestion documentaire et suivi des plans d'action", weight: 1 },
      ]
    },
    {
      id: 12,
      title: 'Fiabilité des données exportées',
      criteria: [
        { text: 'Fiabilité des données exportées', weight: 5 },
      ]
    },
    {
      id: 13,
      title: "Respect de délais de l'envoi",
      criteria: [
        { text: "Respect de délais de l'envoi", weight: 5 },
      ]
    },
  ];

  month = '';
  year = '';
  currentDate = '';

  ngOnInit(): void {
    const months = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin', 'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre'];
    this.month = months[new Date().getMonth()] || 'Janvier';
    this.year = String(new Date().getFullYear());
    this.currentDate = new Date().toLocaleDateString('fr-FR', {
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    });

    this.axesData = this.rawAxesData.map(axe => ({
      ...axe,
      criteria: axe.criteria.map(c => ({ ...c, note: '', obs: '' })),
      collapsed: false,
    }));
  }

  print(): void {
    window.print();
  }

  toggleAxe(axe: IsoAxe): void {
    axe.collapsed = !axe.collapsed;
  }

  updateNote(axe: IsoAxe, index: number): void {
    const cri = axe.criteria[index];
    const num = parseFloat(cri.note);
    if (isNaN(num) || num < 0 || num > 20) {
      cri.note = '';
    } else {
      cri.note = String(Math.min(20, Math.max(0, num)));
    }
  }

  getAxeScore(axe: IsoAxe): number {
    const filled = axe.criteria.filter(c => c.note !== '' && !isNaN(parseFloat(c.note)));
    if (filled.length !== axe.criteria.length) return 0;
    const weightedSum = filled.reduce((sum, c) => sum + (parseFloat(c.note) * c.weight), 0);
    const maxPossible = axe.criteria.reduce((sum, c) => sum + (20 * c.weight), 0);
    return maxPossible > 0 ? (weightedSum / maxPossible) * 20 : 0;
  }

  getAxeTotal(axe: IsoAxe): number {
    return axe.criteria.reduce((sum, c) => {
      const num = parseFloat(c.note);
      return sum + (!isNaN(num) && num >= 0 && num <= 20 ? num * c.weight : 0);
    }, 0);
  }

  getAxeFilled(axe: IsoAxe): number {
    return axe.criteria.filter(c => c.note !== '' && !isNaN(parseFloat(c.note)) && parseFloat(c.note) >= 0 && parseFloat(c.note) <= 20).length;
  }

  getCriterionWeighted(cri: IsoCriterion): string {
    const num = parseFloat(cri.note);
    if (isNaN(num) || num < 0 || num > 20) return '—';
    return (num * cri.weight).toFixed(1);
  }

  get globalScore(): number {
    let totalWeighted = 0;
    let maxPossible = 0;
    for (const axe of this.axesData) {
      for (const cri of axe.criteria) {
        const num = parseFloat(cri.note);
        if (!isNaN(num) && num >= 0 && num <= 20) {
          totalWeighted += num * cri.weight;
        }
        maxPossible += 20 * cri.weight;
      }
    }
    return maxPossible > 0 ? (totalWeighted / maxPossible) * 20 : 0;
  }

  get totalWeighted(): number {
    let total = 0;
    for (const axe of this.axesData) {
      for (const cri of axe.criteria) {
        const num = parseFloat(cri.note);
        if (!isNaN(num) && num >= 0 && num <= 20) {
          total += num * cri.weight;
        }
      }
    }
    return total;
  }

  get maxPossible(): number {
    return this.axesData.reduce((sum, axe) => sum + axe.criteria.reduce((s, c) => s + 20 * c.weight, 0), 0);
  }

  get filledCount(): number {
    return this.axesData.reduce((sum, axe) => sum + this.getAxeFilled(axe), 0);
  }

  get totalCount(): number {
    return this.axesData.reduce((sum, axe) => sum + axe.criteria.length, 0);
  }

  get globalScoreDisplay(): string {
    const filled = this.filledCount;
    const total = this.totalCount;
    if (filled === total && total > 0) return this.globalScore.toFixed(1);
    return '—';
  }

  get hasData(): boolean {
    return this.axesData.some(axe => axe.criteria.some(c => c.note !== '' || c.obs !== ''));
  }

  resetAll(): void {
    if (!confirm('Réinitialiser toutes les notes ?')) return;
    for (const axe of this.axesData) {
      for (const cri of axe.criteria) {
        cri.note = '';
        cri.obs = '';
      }
    }
  }

  cancel(): void {
    this.cancelled.emit();
  }

  save(): void {
    const evaluations: any[] = [];
    for (const axe of this.axesData) {
      for (const cri of axe.criteria) {
        if (cri.note || cri.obs) {
          evaluations.push({
            month: this.month,
            year: this.year,
            filiale: '',
            code: '',
            laboratoire: '',
            axe_evaluation: axe.title,
            criteres: cri.text,
            note: cri.note,
            ponderation: String(cri.weight),
            observations: cri.obs,
          });
        }
      }
    }

    if (!evaluations.length) {
      alert('Remplissez au moins une note ou observation.');
      return;
    }

    const event = new CustomEvent('iso-form-save', { detail: { evaluations } });
    window.dispatchEvent(event);
    this.saved.emit();
  }
}
