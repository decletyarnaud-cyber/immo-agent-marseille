"""
Validation Tab - Composant Streamlit pour l'arbitrage des conflits

Permet a l'utilisateur de:
1. Voir les conflits detectes entre sources
2. Choisir la valeur correcte via radio buttons
3. Saisir manuellement une valeur si necessaire
4. Confirmer ses choix
"""
import streamlit as st
from typing import Dict, List, Optional, Any
from datetime import datetime
from src.storage.models import ConsolidatedAuction, FieldConflict, UserChoice
from src.storage.database import Database


# Mapping des noms de source pour l'affichage
SOURCE_DISPLAY_NAMES = {
    "licitor": "Licitor",
    "encheres_publiques": "Encheres-Publiques",
    "vench": "Vench",
    "manual": "Saisie manuelle",
}

# Labels des champs
FIELD_LABELS = {
    "adresse": "Adresse",
    "code_postal": "Code postal",
    "ville": "Ville",
    "type_bien": "Type de bien",
    "surface": "Surface (m2)",
    "nb_pieces": "Nombre de pieces",
    "nb_chambres": "Nombre de chambres",
    "etage": "Etage",
    "mise_a_prix": "Mise a prix",
    "occupation": "Occupation",
    "cadastre": "Reference cadastrale",
    "avocat_nom": "Nom de l'avocat",
    "avocat_telephone": "Telephone avocat",
    "avocat_email": "Email avocat",
}


def render_validation_tab(auction: ConsolidatedAuction, db: Database):
    """Affiche l'onglet Validation pour une enchere consolidee"""
    unresolved = auction.get_unresolved_conflicts()

    if not unresolved:
        st.success("Aucun conflit a resoudre - toutes les donnees sont validees automatiquement")

        # Afficher les champs valides avec leur source
        st.subheader("Champs valides (consensus)")
        resolved_conflicts = [c for c in auction.conflicts.values() if c.resolved]
        if resolved_conflicts:
            for conflict in resolved_conflicts:
                field_label = FIELD_LABELS.get(conflict.field_name, conflict.field_name)
                source = SOURCE_DISPLAY_NAMES.get(conflict.chosen_source, conflict.chosen_source)
                st.write(f"- **{field_label}**: {conflict.chosen_value} (choisi: {source})")
        return

    # Header avec compteur
    st.warning(f"{len(unresolved)} conflit(s) detecte(s) - Veuillez choisir les bonnes valeurs")

    # Afficher chaque conflit
    for conflict in unresolved:
        render_conflict_resolution(auction, conflict, db)

    st.divider()

    # Bouton pour valider tous les choix
    if st.button("Valider tous les choix", type="primary", use_container_width=True):
        st.success("Choix enregistres !")
        st.rerun()


def render_conflict_resolution(auction: ConsolidatedAuction, conflict: FieldConflict, db: Database):
    """Affiche l'interface de resolution pour un conflit"""
    field_name = conflict.field_name
    field_label = FIELD_LABELS.get(field_name, field_name)

    with st.container():
        st.markdown(f"### Conflit : {field_label}")

        # Construire les options
        options = []
        option_values = {}

        for source, value in conflict.values_by_source.items():
            display_name = SOURCE_DISPLAY_NAMES.get(source, source.title())
            formatted_value = format_value_for_display(value, field_name)
            option_label = f"{display_name}: {formatted_value}"
            options.append(option_label)
            option_values[option_label] = (source, value)

        # Ajouter option saisie manuelle
        manual_option = "Saisie manuelle"
        options.append(manual_option)

        # Radio buttons pour choisir
        col1, col2 = st.columns([3, 1])

        with col1:
            # Determiner la selection par defaut
            default_idx = 0

            selected = st.radio(
                f"Choisir la valeur pour {field_label}",
                options,
                index=default_idx,
                key=f"conflict_{auction.id}_{field_name}",
                label_visibility="collapsed"
            )

            # Champ de saisie manuelle si selectionne
            manual_value = None
            if selected == manual_option:
                manual_value = st.text_input(
                    f"Saisir {field_label}",
                    key=f"manual_{auction.id}_{field_name}",
                    placeholder=f"Entrez la valeur correcte pour {field_label}"
                )

        with col2:
            if st.button("Confirmer", key=f"confirm_{auction.id}_{field_name}"):
                if selected == manual_option:
                    if manual_value:
                        # Sauvegarder le choix manuel
                        save_conflict_resolution(
                            db, auction.id, field_name,
                            manual_value, "manual"
                        )
                        st.success("Choix enregistre !")
                        st.rerun()
                    else:
                        st.error("Veuillez saisir une valeur")
                else:
                    # Sauvegarder le choix
                    source, value = option_values[selected]
                    save_conflict_resolution(
                        db, auction.id, field_name,
                        value, source
                    )
                    st.success("Choix enregistre !")
                    st.rerun()

        st.divider()


def save_conflict_resolution(
    db: Database,
    auction_id: int,
    field_name: str,
    chosen_value: Any,
    chosen_source: str
):
    """Sauvegarde la resolution d'un conflit en base"""
    try:
        db.resolve_consolidated_conflict(
            auction_id=auction_id,
            field_name=field_name,
            chosen_value=chosen_value,
            chosen_source=chosen_source
        )
    except Exception as e:
        st.error(f"Erreur lors de la sauvegarde: {e}")


def format_value_for_display(value: Any, field_name: str) -> str:
    """Formate une valeur pour l'affichage dans les options"""
    if value is None:
        return "(non renseigne)"

    if field_name == "mise_a_prix" and isinstance(value, (int, float)):
        return f"{value:,.0f} EUR"

    if field_name == "surface" and isinstance(value, (int, float)):
        return f"{value} m2"

    if isinstance(value, bool):
        return "Oui" if value else "Non"

    return str(value) if value else "(vide)"


def render_validation_summary(auction: ConsolidatedAuction):
    """Affiche un resume du statut de validation"""
    total_conflicts = len(auction.conflicts)
    resolved = sum(1 for c in auction.conflicts.values() if c.resolved)
    pending = total_conflicts - resolved

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Conflits totaux", total_conflicts)
    with col2:
        st.metric("Resolus", resolved)
    with col3:
        if pending > 0:
            st.metric("En attente", pending)
        else:
            st.metric("En attente", 0)

    # Barre de progression
    if total_conflicts > 0:
        progress = resolved / total_conflicts
        st.progress(progress, text=f"{int(progress * 100)}% complete")
