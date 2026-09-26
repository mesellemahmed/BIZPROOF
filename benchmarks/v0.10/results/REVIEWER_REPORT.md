# BIZPROOF V0.10 Reviewer Certification Report

## Scope

V0.10 certifies selected business-semantic slices only when their locked provenance, V0.7 contract verification evidence, V0.8 source-executed preservation evidence, and V0.9 symbolic equivalence evidence are mutually consistent. CERTIFIED does not mean that the complete external framework has been verified.

## Global result

- Certificates configured: 4
- Certificates issued: 4
- Certificates failed: 0
- External systems: 2
- V0.8 concrete comparisons represented: 52939
- V0.8 correct-adapter mismatches represented: 0
- V0.9 symbolic equivalences represented: 4
- Pipeline result: PASS

## Certificates

### CERT-OF-TA-001

- Status: **CERTIFIED**
- Certification scope: `RETURN_EXPRESSION`
- External system: `openfisca_france`
- Commit: `ebcb7782d17058495c6ca33c278e373e167b641b`
- Source: `openfisca_france/model/prelevements_obligatoires/prelevements_sociaux/taxes_salaires_main_oeuvre.py`
- Adapter: `benchmarks/v0.7/adapters/openfisca_apprenticeship.py`
- Contract: `contracts/external/v0.7/of_apprenticeship_correct.yaml`
- V0.7: `PROVED`
- V0.8: 2 comparisons, 0 correct mismatches
- V0.9: `PROVED` (`unsat`)
- Certified symbolic slice: `def formula(individu, period):
    association = individu('entreprise_est_association_non_lucrative', period)
    return not_(association)`
- Certificate digest: `f046d436e553f8a5a46fcceaa09c1b00c105898aa386ebeb08750c72f9c2c190`

### CERT-OF-TH-001

- Status: **CERTIFIED**
- Certification scope: `RETURN_EXPRESSION_WITH_REPRESENTATION`
- External system: `openfisca_france`
- Commit: `ebcb7782d17058495c6ca33c278e373e167b641b`
- Source: `openfisca_france/model/prelevements_obligatoires/taxe_habitation/taxe_habitation.py`
- Adapter: `benchmarks/v0.7/adapters/openfisca_housing_tax.py`
- Contract: `contracts/external/v0.7/of_housing_tax_correct.yaml`
- V0.7: `PROVED`
- V0.8: 20169 comparisons, 0 correct mismatches
- V0.9: `PROVED` (`unsat`)
- Certified symbolic slice: `def formula_2017_01_01(menage, period, parameters):
    taxe_habitation_commune_epci_avant_degrevement = menage('taxe_habitation_commune_epci_avant_degrevement', period)
    degrevement_plafonnement_taxe_habitation = menage('degrevement_plafonnement_taxe_habitation', period)
    return max_(taxe_habitation_commune_epci_avant_degrevement - degrevement_plafonnement_taxe_habitation, 0)`
- Certificate digest: `f9938f1c41fa80c8a7433e73ff1412614981fc18b30a0e09d0745a355c26998b`

### CERT-OSCAR-PARTIAL-001

- Status: **CERTIFIED**
- Certification scope: `POST_AGGREGATION_THRESHOLD`
- External system: `django_oscar`
- Commit: `5699d78449954f047d6d715fd2b6c5d19594e0f3`
- Source: `src/oscar/apps/offer/conditions.py`
- Adapter: `benchmarks/v0.7/adapters/oscar_count_partial.py`
- Contract: `contracts/external/v0.7/oscar_count_partial_correct.yaml`
- V0.7: `PROVED`
- V0.8: 8256 comparisons, 0 correct mismatches
- V0.9: `PROVED` (`unsat`)
- Certified symbolic slice: `def is_partially_satisfied(self, offer, basket):
    num_matches = self._get_num_matches(basket, offer)
    return 0 < num_matches < self.value`
- Certificate digest: `edc205b70dcf2a4cbaedd3e8cda583df4d50e8aab82b35dd2f1ba150fa791dac`

### CERT-OSCAR-SAT-001

- Status: **CERTIFIED**
- Certification scope: `POST_AGGREGATION_THRESHOLD`
- External system: `django_oscar`
- Commit: `5699d78449954f047d6d715fd2b6c5d19594e0f3`
- Source: `src/oscar/apps/offer/conditions.py`
- Adapter: `benchmarks/v0.7/adapters/oscar_count_satisfied.py`
- Contract: `contracts/external/v0.7/oscar_count_satisfied_correct.yaml`
- V0.7: `PROVED`
- V0.8: 24512 comparisons, 0 correct mismatches
- V0.9: `PROVED` (`unsat`)
- Certified symbolic slice: `num_matches >= self.value`
- Certificate digest: `5426cde635accd91c815d38bbd45abfc9629fc570c84d37d1f8443a0d197290b`

