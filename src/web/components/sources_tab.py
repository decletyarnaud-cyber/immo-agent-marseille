"""
Sources Tab - Composant Streamlit pour afficher la comparaison multi-source

Permet a l'utilisateur de:
1. Voir les sources disponibles pour une enchere
2. Comparer les donnees de chaque source
3. Acceder directement aux pages sources
"""
import streamlit as st
from typing import Dict, List, Optional, Any
from src.storage.models import ConsolidatedAuction, FieldConflict


# Mapping des noms de source pour l'affichage
SOURCE_DISPLAY_NAMES = {
    "licitor": "Licitor",
    "encheres_publiques": "Encheres-Publiques",
    "vench": "Vench",
}

# Champs a comparer avec leurs labels
COMPARISON_FIELDS = [
    ("adresse", "Adresse"),
    ("code_postal", "Code postal"),
    ("ville", "Ville"),
    ("type_bien", "Type de bien"),
    ("surface", "Surface (m2)"),
    ("nb_pieces", "Nb pieces"),
    ("nb_chambres", "Nb chambres"),
    ("etage", "Etage"),
    ("mise_a_prix", "Mise a prix"),
    ("occupation", "Occupation"),
    ("cadastre", "Cadastre"),
    ("avocat_nom", "Avocat"),
    ("avocat_telephone", "Tel. avocat"),
]


def render_sources_tab(auction: ConsolidatedAuction):
    """Affiche l'onglet Sources pour une enchere consolidee"""
    st.subheader("Sources disponibles")

    # Afficher les sources trouvees
    source_cols = st.columns(len(auction.sources) if auction.sources else 1)

    for i, source in enumerate(auction.sources):
        with source_cols[i]:
            display_name = SOURCE_DISPLAY_NAMES.get(source, source.title())
            url = auction.source_urls.get(source, "")

            st.markdown(f"### {display_name}")
            st.success("Trouve")

            if url:
                st.link_button(f"Voir sur {display_name}", url, use_container_width=True)

    # Tableau de comparaison
    st.divider()
    st.subheader("Comparaison des donnees")

    render_comparison_table(auction)

    # Photos par source
    st.divider()
    st.subheader("Photos par source")
    render_photos_by_source(auction)


def render_comparison_table(auction: ConsolidatedAuction):
    """Affiche le tableau de comparaison des donnees entre sources"""
    # Construire les donnees du tableau
    sources = auction.sources
    if not sources:
        st.info("Aucune source disponible")
        return

    # Entete
    header_cols = st.columns([2] + [1] * len(sources))
    header_cols[0].markdown("**Champ**")
    for i, source in enumerate(sources):
        display_name = SOURCE_DISPLAY_NAMES.get(source, source.title())
        header_cols[i + 1].markdown(f"**{display_name}**")

    st.divider()

    # Lignes de comparaison
    for field_name, field_label in COMPARISON_FIELDS:
        row_cols = st.columns([2] + [1] * len(sources))

        # Label du champ avec indicateur de conflit
        has_conflict = field_name in auction.conflicts and not auction.conflicts[field_name].resolved
        if has_conflict:
            row_cols[0].markdown(f"**{field_label}**")
        else:
            row_cols[0].write(field_label)

        # Valeurs par source
        for i, source in enumerate(sources):
            source_data = auction.source_data.get(source)
            if source_data and source_data.raw_data:
                value = source_data.raw_data.get(field_name)
                display_value = format_value(value, field_name)

                # Colorer si conflit
                if has_conflict:
                    row_cols[i + 1].markdown(f"**{display_value}**")
                else:
                    row_cols[i + 1].write(display_value)
            else:
                row_cols[i + 1].write("-")


def render_photos_by_source(auction: ConsolidatedAuction):
    """Affiche les photos groupees par source"""
    for source in auction.sources:
        source_data = auction.source_data.get(source)
        if not source_data or not source_data.raw_data:
            continue

        photos = source_data.raw_data.get("photos", [])
        if not photos:
            continue

        display_name = SOURCE_DISPLAY_NAMES.get(source, source.title())

        with st.expander(f"{display_name} ({len(photos)} photos)", expanded=False):
            # Afficher en grille de 4
            photo_cols = st.columns(4)
            for i, photo in enumerate(photos[:12]):  # Max 12 photos par source
                with photo_cols[i % 4]:
                    try:
                        st.image(photo, use_container_width=True)
                    except:
                        st.write(f"[Photo {i+1}]({photo})")


def format_value(value: Any, field_name: str) -> str:
    """Formate une valeur pour l'affichage"""
    if value is None:
        return "-"

    if field_name == "mise_a_prix" and isinstance(value, (int, float)):
        return f"{value:,.0f} EUR"

    if field_name == "surface" and isinstance(value, (int, float)):
        return f"{value} m2"

    if isinstance(value, bool):
        return "Oui" if value else "Non"

    return str(value) if value else "-"


def render_source_badge(source: str, found: bool = True):
    """Affiche un badge pour une source"""
    display_name = SOURCE_DISPLAY_NAMES.get(source, source.title())

    if found:
        st.success(f"{display_name}")
    else:
        st.error(f"{display_name} (non trouve)")
