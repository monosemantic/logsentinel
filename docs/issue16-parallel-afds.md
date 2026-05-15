\# Issue #16 — Validation des AFDs parallèles par source\_id



\## Objectif



Cette issue vérifie que chaque service surveillé possède son propre état AFD indépendant dans la table `afd\_states`.



La séparation se fait par `source\_id`.



Ainsi, un log reçu pour `service-A` ne doit pas modifier l’état de `service-B` ou de `service-C`.



\## Principe théorique



Chaque service est modélisé par un automate fini déterministe indépendant :



```text

M\_service-A, M\_service-B, M\_service-C, ...

