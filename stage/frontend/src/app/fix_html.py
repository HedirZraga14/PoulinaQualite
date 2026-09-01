with open('app.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the outer } @else { at the same indent level as line 578
target_indent = len(lines[577]) - len(lines[577].lstrip())
start = None
end = None
for i, line in enumerate(lines):
    stripped = line.strip()
    if stripped == '} @else if (connected) {' and start is None:
        start = i
        continue
    if start is not None and stripped == '} @else {' and i > start:
        indent = len(line) - len(line.lstrip())
        if indent == target_indent:
            end = i
            break

print(f'Start: {start+1}, End: {end+1}')

sector_manager_block = '''  } @else if (connected && userRole === 'sector_manager') {
    
    <section class="admin-dashboard reveal-on-scroll reveal-up is-visible">
      <aside class="admin-sidebar reveal-on-scroll reveal-left reveal-delay-1 is-visible">
        <div class="sidebar-header">
          <h2>Mon espace</h2>
          <h4>{{ userFirstName }} {{ userLastName }}</h4>
          <p>Secteur : {{ userSectorName }}</p>
          <p>Espace Responsable de secteur </p>
        </div>
        <nav class="sidebar-nav">
          <button class="sidebar-link" [class.active]="userSection === 'profile'" type="button" (click)="selectUserSection('profile')">Profil</button>
          <button class="sidebar-link" [class.active]="userSection === 'sector_users'" type="button" (click)="selectUserSection('sector_users')">Utilisateurs de mon secteur</button>
          <button class="sidebar-link" [class.active]="userSection === 'evaluations'" type="button" (click)="selectUserSection('evaluations')">Évaluations</button>
          <button class="sidebar-link" type="button" (click)="logout()">Déconnexion</button>
        </nav>
      </aside>
      

      <section class="admin-content reveal-on-scroll reveal-right reveal-delay-2 is-visible">
        @if (userSection === 'profile') {
          <div class="user-profile">
            <h1>Mon profil</h1>
            @if (!isProfileEditing) {
              <div class="profile-card">
                <div class="profile-avatar">
                  <img [src]="userAvatar || '/avatar.png'" alt="Avatar" class="avatar-image">
                </div>
                <p><strong>Nom :</strong> {{ userFirstName }} {{ userLastName }}</p>
                <p><strong>Email :</strong> {{ userEmail || '—' }}</p>
                <p><strong>Secteur :</strong> {{ userSectorName || '—' }}</p>
                <button class="btn-primary" type="button" (click)="editProfile()">Modifier mes informations</button>
                <button class="btn-secondary" type="button" (click)="showPasswordForm = !showPasswordForm">Changer le mot de passe</button>
              </div>
              @if (showPasswordForm) {
                <div class="profile-card">
                  <h3>Changer le mot de passe</h3>
                  <div class="form-group">
                    <label for="currentPassword">Mot de passe actuel</label>
                    <input id="currentPassword" type="password" [(ngModel)]="currentPassword" required>
                  </div>
                  <div class="form-group">
                    <label for="newPassword">Nouveau mot de passe</label>
                    <input id="newPassword" type="password" [(ngModel)]="newPassword" required>
                  </div>
                  <button class="btn-primary" type="button" (click)="changePassword()">Enregistrer le mot de passe</button>
                  <button class="btn-secondary" type="button" (click)="showPasswordForm = false">Annuler</button>
                  @if (passwordError) {
                    <p class="error">{{ passwordError }}</p>
                  }
                  @if (passwordSuccess) {
                    <p class="success">{{ passwordSuccess }}</p>
                  }
                </div>
              }
            } @else {
              <div class="profile-card">
                <h3>Modifier mes informations</h3>
                <div class="profile-avatar">
                  <img [src]="userAvatar || '/avatar.png'" alt="Avatar" class="avatar-image">
                </div>
                <div class="form-group">
                  <label for="avatar">Avatar</label>
                  <input id="avatar" type="file" accept="image/*" (change)="onAvatarChange($event)">
                </div>
                <div class="form-group">
                  <label for="firstName">Prénom</label>
                  <input id="firstName" type="text" [(ngModel)]="userFirstName" required>
                </div>
                <div class="form-group">
                  <label for="lastName">Nom</label>
                  <input id="lastName" type="text" [(ngModel)]="userLastName" required>
                </div>
                <div class="form-group">
                  <label for="email">Email</label>
                  <input id="email" type="email" [(ngModel)]="userEmail" required>
                </div>
                <button class="btn-primary" type="button" (click)="saveProfile()">Enregistrer</button>
                <button class="btn-secondary" type="button" (click)="cancelProfileEdit()">Annuler</button>
                @if (profileError) {
                  <p class="error">{{ profileError }}</p>
                }
                @if (profileSuccess) {
                  <p class="success">{{ profileSuccess }}</p>
                }
              </div>
            }
          </div>
          
          } @else if (userSection === 'sector_users') {
          <section class="user-management">
            <div class="branch-actions">
              <div class="branch-search">
                <label for="sectorUserSearch">Rechercher un utilisateur</label>
                <input id="sectorUserSearch" type="text" [(ngModel)]="sectorUserSearch" placeholder="Nom, prénom, e-mail ou filiale">
              </div>
            </div>
            <div class="branch-list">
              <table>
                <thead>
                  <tr>
                    <th>Nom</th>
                    <th>Prénom</th>
                    <th>Email</th>
                    <th>Filiale</th>
                  </tr>
                </thead>
                <tbody>
                  @for (user of filteredSectorUsers; track user.id) {
                    <tr>
                      <td>{{ user.last_name }}</td>
                      <td>{{ user.first_name }}</td>
                      <td>{{ user.email }}</td>
                      <td>{{ user.branch__name || '—' }}</td>
                    </tr>
                  }
                </tbody>
              </table>
            </div>
          </section>
          } @else if (userSection === 'evaluations') {
            
            <section class="evaluations-management">
              <div class="evaluation-import-panel">
                <div class="evaluation-import-intro">
                  <span class="evaluation-section-badge">Liste</span>
                  <h2>Évaluations de mon secteur</h2>
                  <p>Consultez toutes les évaluations de votre secteur et mettez à jour les notes et observations.</p>
                  <div class="evaluation-toolbar">
                    <button class="btn-secondary" type="button" (click)="exportEvaluationPdf()" [disabled]="filteredEvaluations.length === 0">Exporter PDF</button>
                    <button class="btn-primary" type="button" (click)="loadEvaluations()">Actualiser</button>
                  </div>
                  @if (evaluationSuccess) {
                    <p class="success">{{ evaluationSuccess }}</p>
                  }
                  @if (evaluationError) {
                    <p class="error">{{ evaluationError }}</p>
                  }
                  @if (evaluationSaveMessage) {
                    <p class="success">{{ evaluationSaveMessage }}</p>
                  }
                  @if (evaluationSaveError) {
                    <p class="error">{{ evaluationSaveError }}</p>
                  }
                </div>
              </div>

              @if (filteredEvaluations.length === 0) {
                <div class="admin-placeholder">
                  <p>Aucune évaluation enregistrée dans votre secteur.</p>
                </div>
              }

              @if (filteredEvaluations.length > 0) {
                <div class="evaluation-groups">
                  @for (group of evaluationAxisGroups; track group.axis) {
                    <div class="evaluation-axis-panel">
                      <div class="evaluation-axis-header">
                        <div>
                          <span class="evaluation-section-badge">{{ group.axis }}</span>
                          <h3>{{ group.axis }}</h3>
                        </div>
                        <span class="evaluation-group-count">{{ group.total }} évaluation(s)</span>
                      </div>
                      <div class="evaluation-table-wrapper">
                        <table class="evaluation-table evaluation-list-table">
                          <thead>
                            <tr>
                              <th>Filiale</th>
                              <th>Axe d'évaluation</th>
                              <th>Critères</th>
                              <th>Note /20</th>
                              <th>Observations</th>
                              <th>Actions</th>
                            </tr>
                          </thead>
                          <tbody>
                            @for (evaluation of group.rows; track evaluation.id || $index) {
                              <tr>
                                <td>{{ evaluation.filiale_name || '—' }}</td>
                                <td class="evaluation-axis-cell">{{ evaluation.axe_evaluation || 'Sans axe' }}</td>
                                <td class="evaluation-criteria-cell">{{ evaluation.criteres || '—' }}</td>
                                <td>
                                  @if (evaluation.editing) {
                                    <input class="evaluation-input" type="text" [(ngModel)]="evaluation.note" placeholder="Note /20">
                                  } @else {
                                    {{ evaluation.note || '—' }}
                                  }
                                </td>
                                <td>
                                  @if (evaluation.editing) {
                                    <textarea class="evaluation-textarea" [(ngModel)]="evaluation.observations" placeholder="Observations"></textarea>
                                  } @else {
                                    <span class="evaluation-observations-cell">{{ evaluation.observations || '—' }}</span>
                                  }
                                </td>
                                <td class="evaluation-row-actions">
                                  @if (evaluation.editing) {
                                    <button class="btn-primary" type="button" (click)="saveEvaluationRow(evaluation)">Enregistrer</button>
                                    <button class="btn-ghost" type="button" (click)="cancelEditEvaluation(evaluation)">Annuler</button>
                                  } @else {
                                    <button class="btn-secondary" type="button" (click)="editEvaluationRow(evaluation)">Modifier</button>
                                  }
                                </td>
                              </tr>
                            }
                          </tbody>
                        </table>
                      </div>
                    </div>
                  }
                </div>
              }
            </section>
          }
        </section>
      </section>
    </section>
    
'''

user_block = '''  } @else if (connected && userRole === 'user') {
    
    <section class="admin-dashboard reveal-on-scroll reveal-up is-visible">
      <aside class="admin-sidebar reveal-on-scroll reveal-left reveal-delay-1 is-visible">
        <div class="sidebar-header">
          <h2>Mon espace</h2>
          <h4>Secteur : {{ userSectorName }}</h4>
          <h4>Filiale : {{ userBranchName }}</h4>
          <p>Espace utilisateur</p>
        </div>
        <nav class="sidebar-nav">
          <button class="sidebar-link" [class.active]="userSection === 'profile'" type="button" (click)="selectUserSection('profile')">Profil</button>
          <button class="sidebar-link" [class.active]="userSection === 'evaluations'" type="button" (click)="selectUserSection('evaluations')">Évaluations</button>
          <button class="sidebar-link" type="button" (click)="logout()">Déconnexion</button>
        </nav>
      </aside>
      

      <section class="admin-content reveal-on-scroll reveal-right reveal-delay-2 is-visible">
        @if (userSection === 'profile') {
          <div class="user-profile">
            <h1>Mon profil</h1>
            @if (!isProfileEditing) {
              <div class="profile-card">
                <div class="profile-avatar">
                  <img [src]="userAvatar || '/avatar.png'" alt="Avatar" class="avatar-image">
                </div>
                <p><strong>Nom :</strong> {{ userFirstName }} {{ userLastName }}</p>
                <p><strong>Email :</strong> {{ userEmail || '—' }}</p>
                <p><strong>Secteur :</strong> {{ userSectorName || '—' }}</p>
                <button class="btn-primary" type="button" (click)="editProfile()">Modifier mes informations</button>
                <button class="btn-secondary" type="button" (click)="showPasswordForm = !showPasswordForm">Changer le mot de passe</button>
              </div>
              @if (showPasswordForm) {
                <div class="profile-card">
                  <h3>Changer le mot de passe</h3>
                  <div class="form-group">
                    <label for="currentPassword">Mot de passe actuel</label>
                    <input id="currentPassword" type="password" [(ngModel)]="currentPassword" required>
                  </div>
                  <div class="form-group">
                    <label for="newPassword">Nouveau mot de passe</label>
                    <input id="newPassword" type="password" [(ngModel)]="newPassword" required>
                  </div>
                  <button class="btn-primary" type="button" (click)="changePassword()">Enregistrer le mot de passe</button>
                  <button class="btn-secondary" type="button" (click)="showPasswordForm = false">Annuler</button>
                  @if (passwordError) {
                    <p class="error">{{ passwordError }}</p>
                  }
                  @if (passwordSuccess) {
                    <p class="success">{{ passwordSuccess }}</p>
                  }
                </div>
              }
            } @else {
              <div class="profile-card">
                <h3>Modifier mes informations</h3>
                <div class="profile-avatar">
                  <img [src]="userAvatar || '/avatar.png'" alt="Avatar" class="avatar-image">
                </div>
                <div class="form-group">
                  <label for="avatar">Avatar</label>
                  <input id="avatar" type="file" accept="image/*" (change)="onAvatarChange($event)">
                </div>
                <div class="form-group">
                  <label for="firstName">Prénom</label>
                  <input id="firstName" type="text" [(ngModel)]="userFirstName" required>
                </div>
                <div class="form-group">
                  <label for="lastName">Nom</label>
                  <input id="lastName" type="text" [(ngModel)]="userLastName" required>
                </div>
                <div class="form-group">
                  <label for="email">Email</label>
                  <input id="email" type="email" [(ngModel)]="userEmail" required>
                </div>
                <button class="btn-primary" type="button" (click)="saveProfile()">Enregistrer</button>
                <button class="btn-secondary" type="button" (click)="cancelProfileEdit()">Annuler</button>
                @if (profileError) {
                  <p class="error">{{ profileError }}</p>
                }
                @if (profileSuccess) {
                  <p class="success">{{ profileSuccess }}</p>
                }
              </div>
            }
          </div>
          
          } @else if (userSection === 'evaluations') {
          
            <section class="evaluations-management">
              @if (!isChecklistMode && !showIsoForm) {
                <div class="evaluation-import-panel">
                  <div class="evaluation-import-intro">
                    <span class="evaluation-section-badge">Liste</span>
                    <h2>Mes évaluations</h2>
                    <p>Consultez vos évaluations par axe et par critères, et ajoutez de nouvelles évaluations.</p>
                     <div class="evaluation-toolbar">
                       <button class="btn-primary" type="button" (click)="openIsoForm()">Ajouter évaluation</button>
                       <button class="btn-secondary" type="button" (click)="exportEvaluationPdf()" [disabled]="evaluations.length === 0">Exporter PDF</button>
                       <button class="btn-primary" type="button" (click)="loadEvaluations()">Actualiser</button>
                     </div>
                    @if (evaluationSuccess) {
                      <p class="success">{{ evaluationSuccess }}</p>
                    }
                    @if (evaluationError) {
                      <p class="error">{{ evaluationError }}</p>
                    }
                  </div>
                </div>

                @if (evaluations.length > 0) {
                  <div class="evaluation-stats">
                    <div class="stat-card">
                      <span class="stat-value">{{ userEvaluationStats.total }}</span>
                      <span class="stat-label">Évaluations réalisées</span>
                    </div>
                    <div class="stat-card">
                      <span class="stat-value">{{ userEvaluationStats.avgConformite }}%</span>
                      <span class="stat-label">Conformité moyenne</span>
                    </div>
                    <div class="stat-card">
                      <span class="stat-value">{{ userEvaluationStats.bestNote ?? '—' }}</span>
                      <span class="stat-label">Meilleure note</span>
                    </div>
                    <div class="stat-card">
                      <span class="stat-value">{{ userEvaluationStats.minNote ?? '—' }}</span>
                      <span class="stat-label">Note minimum</span>
                    </div>
                  </div>
                }

                @if (evaluations.length === 0) {
                  <div class="admin-placeholder">
                    <p>Aucune évaluation enregistrée. Cliquez sur "Ajouter évaluation" pour commencer.</p>
                  </div>
                }

                @if (evaluations.length > 0) {
                  <div class="evaluation-groups">
                    @for (group of groupedEvaluations; track group.axe) {
                      <div class="evaluation-axis-panel">
                        <div class="evaluation-axis-header">
                          <div>
                            <span class="evaluation-section-badge">{{ group.axe }}</span>
                            <h3>{{ group.axe }}</h3>
                          </div>
                          <span class="evaluation-group-count">{{ group.rows.length }} évaluation(s)</span>
                        </div>
                        <div class="evaluation-table-wrapper">
                          <table class="evaluation-table evaluation-list-table">
                            <thead>
                              <tr>
                                <th>Critères</th>
                                <th>Note /20</th>
                                <th>Pondération</th>
                                <th>Moyenne</th>
                                <th>Conformité %</th>
                                <th>Observations</th>
                                <th>Actions</th>
                              </tr>
                            </thead>
                            <tbody>
                              @for (evaluation of group.rows; track evaluation.id || $index) {
                                <tr>
                                  <td class="evaluation-criteria-cell">{{ evaluation.criteres || '—' }}</td>
                                  <td>
                                    @if (evaluation.editing) {
                                      <input class="evaluation-input" type="text" [(ngModel)]="evaluation.note" placeholder="Note /20">
                                    } @else {
                                      {{ evaluation.note || '—' }}
                                    }
                                  </td>
                                  <td>
                                    @if (evaluation.editing) {
                                      <input class="evaluation-input" type="text" [(ngModel)]="evaluation.ponderation" placeholder="Pondération">
                                    } @else {
                                      {{ evaluation.ponderation || '—' }}
                                    }
                                  </td>
                                  <td>{{ evaluation.moyenne_axe ?? '—' }}</td>
                                  <td>{{ evaluation.conformite_axe ?? '—' }}%</td>
                                  <td>
                                    @if (evaluation.editing) {
                                      <textarea class="evaluation-textarea" [(ngModel)]="evaluation.observations" placeholder="Observations"></textarea>
                                    } @else {
                                      <span class="evaluation-observations-cell">{{ evaluation.observations || '—' }}</span>
                                    }
                                  </td>
                                  <td class="evaluation-row-actions">
                                    @if (evaluation.editing) {
                                      <button class="btn-primary" type="button" (click)="saveEvaluationRow(evaluation)">Enregistrer</button>
                                      <button class="btn-ghost" type="button" (click)="cancelEditEvaluation(evaluation)">Annuler</button>
                                    } @else {
                                      <button class="btn-secondary" type="button" (click)="editEvaluationRow(evaluation)">Modifier</button>
                                      <button class="btn-ghost" type="button" (click)="deleteEvaluation(evaluation, $index)">Supprimer</button>
                                    }
                                  </td>
                                </tr>
                              }
                            </tbody>
                          </table>
                        </div>
                      </div>
                    }
                  </div>
                }
              } @else if (showIsoForm) {
                <app-iso-form (saved)="showIsoForm = false" (cancelled)="showIsoForm = false"></app-iso-form>
              } @else {
                <div class="checklist-wrapper">
                  <div class="checklist-header">
                    <span class="evaluation-section-badge">Checklist</span>
                    <h2>Grille d'évaluation ISO 17025 – Laboratoire</h2>
                    <p>Remplissez les notes et observations pour chaque critère.</p>
                    <div class="checklist-toolbar">
                      <label>
                        <span class="filter-label">Mois</span>
                        <select [(ngModel)]="checklistMonth">
                          @for (m of ['Janvier','Février','Mars','Avril','Mai','Juin','Juillet','Août','Septembre','Octobre','Novembre','Décembre']; track m) {
                            <option [ngValue]="m">{{ m }}</option>
                          }
                        </select>
                      </label>
                      <label>
                        <span class="filter-label">Année</span>
                        <input type="number" [(ngModel)]="checklistYear" placeholder="Année">
                      </label>
                    </div>
                  </div>

                  @if (evaluationError) {
                    <p class="error">{{ evaluationError }}</p>
                  }
                  @if (evaluationSaveError) {
                    <p class="error">{{ evaluationSaveError }}</p>
                  }
                  @if (evaluationSaveMessage) {
                    <p class="success">{{ evaluationSaveMessage }}</p>
                  }

                  @if (checklistAxes.length === 0) {
                    <div class="admin-placeholder">
                      <p>Chargement de la checklist...</p>
                    </div>
                  }

                  @if (checklistAxes.length > 0) {
                    <div class="checklist-iso-container">
                      <div class="checklist-summary-bar">
                        <div class="checklist-stat">
                          <span class="checklist-label">Score global</span>
                          <span class="checklist-value" [class.green]="checklistGlobalScore >= 16" [class.orange]="checklistGlobalScore >= 10 && checklistGlobalScore < 16" [class.red]="checklistGlobalScore < 10 && checklistGlobalScore > 0">{{ checklistGlobalScoreDisplay }}</span>
                          <span style="font-size:0.9rem;color:#5a6f84;">/ 20</span>
                        </div>
                        <div class="checklist-stat">
                          <span class="checklist-label">Total pondéré</span>
                          <span class="checklist-value">{{ checklistTotalWeighted }}</span>
                        </div>
                        <div class="checklist-stat">
                          <span class="checklist-label">Max possible</span>
                          <span class="checklist-value">{{ checklistMaxPossible }}</span>
                        </div>
                        <div class="checklist-stat">
                          <span class="checklist-label">Critères évalués</span>
                          <span class="checklist-value">{{ checklistFilledCount }}</span>
                          <span style="font-size:0.9rem;color:#5a6f84;">/ {{ checklistTotalCount }}</span>
                        </div>
                      </div>

                      @for (axe of checklistAxes; track axe.title) {
                        <div class="axe-card">
                          <div class="axe-header" (click)="toggleAxe(axe)">
                            <div class="axe-title">
                              <span class="num">{{ $index + 1 }}</span>
                              {{ axe.title }}
                              <span class="axe-crit-count">({{ axe.criteria.length }} crit.)</span>
                            </div>
                              <div class="axe-score">
                                <span class="axe-score-label">Score</span>
                                <span class="score-badge" [class.high]="getChecklistAxeFilled(axe) === axe.criteria.length && getChecklistAxeScore(axe) >= 16" [class.medium]="getChecklistAxeFilled(axe) === axe.criteria.length && getChecklistAxeScore(axe) >= 10 && getChecklistAxeScore(axe) < 16" [class.low]="getChecklistAxeFilled(axe) === axe.criteria.length && getChecklistAxeScore(axe) < 10 && getChecklistAxeFilled(axe) > 0">
                                  {{ getChecklistAxeFilled(axe) === axe.criteria.length ? getChecklistAxeScore(axe).toFixed(1) : '—' }}
                                </span>
                                <span class="axe-score-max">/ 20</span>
                                <span class="toggle-icon" [class.open]="!axe.collapsed">▾</span>
                              </div>
                          </div>
                          <div class="axe-body" [class.collapsed]="axe.collapsed">
                            <table class="criteria-table">
                              <thead>
                                <tr>
                                  <th>Critère</th>
                                  <th class="text-center">Note / 20</th>
                                  <th class="text-center">Pond.</th>
                                  <th class="text-center">Score pond.</th>
                                  <th>Observations</th>
                                </tr>
                              </thead>
                              <tbody>
                                @for (cri of axe.criteria; track cri.text) {
                                  <tr>
                                    <td class="criterion-text">{{ cri.text }}</td>
                                    <td class="text-center">
                                      <input type="number" class="note-input" min="0" max="20" step="1" [(ngModel)]="cri.note" placeholder="0-20">
                                    </td>
                                    <td class="text-center weight-cell">× {{ cri.weight }}</td>
                                    <td class="text-center weighted-score">{{ getChecklistCriterionWeighted(cri) }}</td>
                                    <td>
                                      <input type="text" class="obs-input" [(ngModel)]="cri.obs" placeholder="Observations…">
                                    </td>
                                  </tr>
                                }
                              </tbody>
                            </table>
                            <div class="axe-footer">
                              <span class="total-label">Total de l'axe</span>
                              <span class="total-value" [class.high]="getChecklistAxeFilled(axe) === axe.criteria.length && getChecklistAxeScore(axe) >= 16" [class.medium]="getChecklistAxeFilled(axe) === axe.criteria.length && getChecklistAxeScore(axe) >= 10 && getChecklistAxeScore(axe) < 16" [class.low]="getChecklistAxeFilled(axe) === axe.criteria.length && getChecklistAxeScore(axe) < 10 && getChecklistAxeFilled(axe) > 0">
                                {{ getChecklistAxeFilled(axe) === axe.criteria.length ? getChecklistAxeTotal(axe).toFixed(1) : '—' }}
                              </span>
                              <span class="max-possible">/ {{ axe.criteria.reduce((sum, c) => sum + 20 * c.weight, 0).toFixed(0) }}</span>
                              <span class="axe-filled-count">{{ getChecklistAxeFilled(axe) }}/{{ axe.criteria.length }} renseignés</span>
                            </div>
                          </div>
                        </div>
                      }

                      <div class="checklist-actions-bar">
                        <button class="btn btn-secondary" type="button" (click)="cancelChecklist()">Annuler</button>
                        <button class="btn btn-success" type="button" (click)="saveChecklist()">Enregistrer l'audit</button>
                      </div>
                    </div>
                  }
                </div>
              }
            </section>
          }
        </section>
      </section>
    </section>
    
'''

new_content = ''.join(lines[:start]) + sector_manager_block + user_block + ''.join(lines[end:])

with open('app.html', 'w', encoding='utf-8') as f:
    f.write(new_content)

print('Done')
