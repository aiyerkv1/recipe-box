import streamlit as st
import pandas as pd
import json
import os
import re
from streamlit_gsheets import GSheetsConnection

# --- Data Management (Now using Google Sheets!) ---
def get_connection():
    return st.connection("gsheets", type=GSheetsConnection)

def load_recipes():
    try:
        conn = get_connection()
        # Read the sheet into a Pandas DataFrame
        df = conn.read(worksheet="Recipes", usecols=[0, 1, 2])
        df = df.dropna(how="all") # Drop completely empty rows
        
        recipes = []
        for _, row in df.iterrows():
            recipes.append({
                "name": str(row["name"]) if pd.notna(row["name"]) else "",
                # We store ingredients as a JSON string in the sheet so we must decode it
                "ingredients": json.loads(row["ingredients"]) if pd.notna(row["ingredients"]) and str(row["ingredients"]).strip() != "" else [],
                "instructions": str(row["instructions"]) if pd.notna(row["instructions"]) else ""
            })
        return recipes
    except Exception as e:
        return []

def save_recipes(recipes):
    conn = get_connection()
    # Convert our Python list back into a DataFrame
    df_data = []
    for r in recipes:
        df_data.append({
            "name": r["name"],
            "ingredients": json.dumps(r.get("ingredients", [])), # Encode to string for the sheet cell
            "instructions": r["instructions"]
        })
    df = pd.DataFrame(df_data)
    conn.update(worksheet="Recipes", data=df)

def load_groceries():
    try:
        conn = get_connection()
        df = conn.read(worksheet="Groceries", usecols=[0, 1])
        df = df.dropna(how="all")
        
        groceries = []
        for _, row in df.iterrows():
            groceries.append({
                "Bought": bool(row["Bought"]) if pd.notna(row["Bought"]) else False,
                "Item": str(row["Item"]) if pd.notna(row["Item"]) else ""
            })
        return groceries
    except:
        return []

def save_groceries(groceries):
    conn = get_connection()
    df = pd.DataFrame(groceries)
    # Ensure columns exist even if empty
    if df.empty:
        df = pd.DataFrame(columns=["Bought", "Item"])
    conn.update(worksheet="Groceries", data=df)

def clean_text(text):
    if not text: return ""
    artifact_pattern = r'\[cite.*?\]|cite:\s*\d+|cite:number|:\s*number|\[\d+\]|\[:\s*\d+\]'
    cleaned = re.sub(artifact_pattern, '', str(text), flags=re.IGNORECASE)
    return re.sub(r'\s{2,}', ' ', cleaned).strip()

# --- Pop-Up Windows (Dialogs) ---
@st.dialog("Recipe Details", width="large")
def view_recipe_dialog(recipe):
    st.title(clean_text(recipe['name']).title())
    st.divider()
    col_ing, col_inst = st.columns([1, 2])
    
    with col_ing:
        st.subheader("Ingredients")
        for ing in recipe.get('ingredients', []):
            amt = clean_text(ing.get('amount', '')).title()
            item = clean_text(ing.get('item', '')).title()
            st.write(f"**{amt}** {item}")
            
    with col_inst:
        st.subheader("Instructions")
        st.markdown(f'<div style="white-space: pre-wrap;">{clean_text(recipe.get("instructions", ""))}</div>', unsafe_allow_html=True)

@st.dialog("Recipe Editor", width="large")
def edit_recipe_dialog(recipe_to_edit=None):
    is_editing = recipe_to_edit is not None
    r_data = recipe_to_edit if is_editing else {"name": "", "ingredients": [{"amount": "", "item": ""}], "instructions": ""}
    
    name = st.text_input("Recipe Name", value=clean_text(r_data.get('name', '')).title())
    
    formatted_ingredients = []
    for ing in r_data.get('ingredients', [{"amount": "", "item": ""}]):
        formatted_ingredients.append({
            "amount": clean_text(ing.get('amount', '')).title(),
            "item": clean_text(ing.get('item', '')).title()
        })

    ingredients = st.data_editor(
        formatted_ingredients,
        column_config={"amount": "Amount", "item": "Ingredient"},
        num_rows="dynamic", width="stretch", key="ing_editor"
    )
    
    instructions = st.text_area("Instructions", value=clean_text(r_data.get('instructions', '')), height=300)
    
    if st.button("Save Recipe", type="primary", use_container_width=True):
        if name:
            clean_ingredients = [
                {"amount": clean_text(ing.get('amount', '')).title(), "item": clean_text(ing.get('item', '')).title()} 
                for ing in ingredients if str(ing.get('item', '')).strip()
            ]
            new_recipe = {"name": clean_text(name).title(), "ingredients": clean_ingredients, "instructions": instructions}
            
            recipes = load_recipes()
            if is_editing:
                recipes = [r for r in recipes if r['name'] != r_data['name']]
            recipes.append(new_recipe)
            save_recipes(recipes)
            st.rerun()

# --- Main App ---
def main():
    st.set_page_config(page_title="My Recipes", layout="wide")

    with st.sidebar:
        st.header("Settings")
        text_size = st.slider("Font Size (px)", 14, 30, 18)
        st.markdown(f"<style>div, p, li, span, td {{ font-size: {text_size}px !important; }}</style>", unsafe_allow_html=True)

    st.title("My Recipes")
    
    tab_lib, tab_groc = st.tabs(["Recipe Library", "Grocery List"])

    # --- TAB 1: LIBRARY ---
    with tab_lib:
        recipes = load_recipes()
        
        if st.button("Create New Recipe", type="primary"):
            edit_recipe_dialog() 
            
        search_query = st.text_input("Search by recipe name or ingredients (e.g., chickpeas, coconut)", placeholder="Type to search...").lower()
        st.divider()

        filtered = []
        if search_query:
            pantry = [t.strip() for t in search_query.split(",") if t.strip()]
            for r in recipes:
                if search_query in r.get('name', '').lower():
                    filtered.append(r)
                    continue
                r_ings = [i.get('item', '').lower() for i in r.get('ingredients', [])]
                if all(any(p in r_i for r_i in r_ings) for p in pantry):
                    filtered.append(r)
        else:
            filtered = recipes

        filtered = sorted(filtered, key=lambda x: clean_text(x.get('name', '')).lower())

        if not filtered:
            st.info("No recipes found.")
        else:
            col1, col2 = st.columns(2)
            
            for i, recipe in enumerate(filtered):
                target_col = col1 if i % 2 == 0 else col2
                
                with target_col:
                    with st.expander(clean_text(recipe.get('name', '')).title()):
                        c1, c2, c3 = st.columns(3)
                        
                        with c1:
                            if st.button("View", key=f"v_{i}", use_container_width=True):
                                view_recipe_dialog(recipe)
                        with c2:
                            if st.button("Cart", key=f"g_{i}", use_container_width=True):
                                groceries = load_groceries()
                                groceries.extend([{
                                    "Bought": False, 
                                    "Item": f"{clean_text(ing.get('amount', '')).title()} {clean_text(ing.get('item', '')).title()}".strip()
                                } for ing in recipe.get('ingredients', [])])
                                save_groceries(groceries)
                                st.success("Added!")
                        with c3:
                            if st.button("Edit", key=f"e_{i}", use_container_width=True):
                                edit_recipe_dialog(recipe)

    # --- TAB 2: GROCERIES ---
    with tab_groc:
        with st.form("quick_add_grocery", clear_on_submit=True):
            col_input, col_btn = st.columns([0.8, 0.2])
            with col_input:
                new_groc = st.text_input("Quick add", label_visibility="collapsed", placeholder="Add an item...")
            with col_btn:
                if st.form_submit_button("Add Item", use_container_width=True) and new_groc.strip():
                    groceries = load_groceries()
                    groceries.append({"Bought": False, "Item": clean_text(new_groc).title()})
                    save_groceries(groceries)
                    st.rerun()
                    
        groceries = load_groceries()
        edited = st.data_editor(
            groceries,
            column_config={
                "Bought": st.column_config.CheckboxColumn("Done", default=False), 
                "Item": st.column_config.TextColumn("Ingredient", width="large")
            },
            hide_index=True, num_rows="dynamic", width="stretch"
        )
        
        if edited != groceries:
            save_groceries(edited)
            st.rerun()
            
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Clear Completed", use_container_width=True):
                save_groceries([g for g in edited if not g.get('Bought', False)])
                st.rerun()
        with c2:
            if st.button("Delete Entire List", type="primary", use_container_width=True):
                save_groceries([])
                st.rerun()

if __name__ == "__main__":
    main()
