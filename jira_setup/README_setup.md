# Jira Setup Scripts

Scripts utilisés pour créer et enrichir le projet Jira (Étape 1).

## ⚠️ IMPORTANT

Ces scripts ont **déjà été exécutés**. Le projet SCRUM contient 306 tickets.
**Ne pas relancer** sauf si vous voulez repartir de zéro.

## Ordre d'exécution (si reset)

```bash
# 1. Génération initiale (~200 tickets)
python jira_setup/seed_tickets.py

# 2. Enrichissement (descriptions, labels, versions, commentaires)
python jira_setup/enrich_tickets.py

# 3. Améliorations avancées (sprints, workflow, cascade)
python jira_setup/advanced_enrich.py
```

## Ce que chaque script fait

### seed_tickets.py
- Crée 4 Epics automotive (Infotainment, Diagnostics, OTA, CAN)
- Crée Stories, Tasks, Bugs, Subtasks par epic
- Ajoute labels, priorités, story points
- Crée les dépendances de base

### enrich_tickets.py
- Descriptions techniques réalistes (Steps to reproduce, AC, CAN frames)
- 4 Fix versions (v1.0 → v2.0)
- Assignees (3 personas)
- Dépendances complexes en cascade (4 niveaux)
- Commentaires multi-tours (dev ↔ QA ↔ tech lead)
- 2 nouveaux Epics (Safety/AUTOSAR + Power Management)
- Time tracking & worklogs
- Labels custom (SEV1, BENCH, ECU_ID, CAN_Frame)

### advanced_enrich.py
- 4 sprints (3 fermés + 1 actif avec vélocité)
- Workflow transitions réalistes (reopen, rejected, blocked)
- Blocage en cascade avec root cause documenté
- Roadmap avec overdue intentionnels
- 5 composants Jira
- Tickets régression liés aux bugs originaux
- 12 test scenarios (PASS/FAIL/BLOCKED)
- 10 tech debt + 10 improvements en backlog

## Résultat final

| Métrique | Valeur |
|----------|--------|
| Total tickets | 306 |
| Epics | 6 |
| Sprints | 4 (3 closed + 1 active) |
| Fix versions | 4 |
| Composants | 5 |
| Tickets bloqués | 27 |
| Bugs critiques | 9 |
| Overdue | 49 |