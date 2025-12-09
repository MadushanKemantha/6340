import streamlit as st
import json
from datetime import datetime, timedelta
import os
import re
import pandas as pd
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ========== BACKEND ASSISTANT CLASS ==========
class GroceryAssistant:
    def __init__(self, use_llm=False, api_key=""):
        self.filename = "grocery_data.json"
        self.use_llm = use_llm
        self.api_key = api_key
        self.model = None
        self.model_name = "Unknown"
        self.last_error = None  # Store errors to show in UI

        # --- CONFIGURE GEMINI (AUTO-DETECT MODE) ---
        if self.use_llm and self.api_key:
            try:
                genai.configure(api_key=self.api_key)
                
                # 1. Ask Google what models are available for this Key
                all_models = list(genai.list_models())
                
                # 2. Find models that can generate text (generateContent)
                valid_models = [m.name for m in all_models if 'generateContent' in m.supported_generation_methods]
                
                if not valid_models:
                    self.last_error = "No compatible models found for this Key."
                else:
                    # 3. Smart Selection: Prefer Flash -> Pro -> 1.0 -> Any
                    preferred_order = [
                        'models/gemini-1.5-flash', 
                        'models/gemini-pro', 
                        'models/gemini-1.0-pro',
                        'models/gemini-1.5-pro'
                    ]
                    
                    selected_model = valid_models[0] # Default to first one found
                    
                    # Try to find a preferred model
                    for p in preferred_order:
                        if p in valid_models:
                            selected_model = p
                            break
                    
                    self.model_name = selected_model
                    self.model = genai.GenerativeModel(selected_model)
                    
            except Exception as e:
                self.last_error = f"Setup Error: {str(e)}"
                print(f"Gemini Setup Error: {e}")

        self.load_data()
        
        # Default knowledge base
        self.default_expiry_days = {
            "milk": 7, "eggs": 14, "bread": 5, "cheese": 10,
            "yogurt": 10, "meat": 3, "fish": 2, "vegetables": 7, "fruits": 5
        }
        
        if "learned_expiry" not in self.data:
            self.data["learned_expiry"] = {}

        self.expiry_map = {**self.default_expiry_days, **self.data["learned_expiry"]}

        self.healthier_options = {
            "white bread": "whole wheat bread 🍞", "soda": "sparkling water 💧",
            "chips": "air-popped popcorn 🌰", "sugar": "honey 🍯",
            "butter": "olive oil 🥑", "white rice": "brown rice 🍚",
            "milk chocolate": "dark chocolate 🍫", "ice cream": "frozen yogurt 🍨",
            "mayonnaise": "greek yogurt 🥣"
        }
        
        self.item_pairings = {
            "bread": ["butter", "jam"], "coffee": ["milk", "sugar"],
            "pasta": ["pasta sauce", "cheese"], "eggs": ["bread", "butter"],
            "cereal": ["milk"], "pancake": ["syrup"],
        }

    def load_data(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r') as f:
                    self.data = json.load(f)
            except:
                self.data = self.default_data()
        else:
            self.data = self.default_data()
    
    def default_data(self):
        return {
            "grocery_list": [], "purchase_history": [], "last_purchase": {},
            "learned_expiry": {}, "user_preferences": {"diet": "None"}
        }
    
    def save_data(self):
        with open(self.filename, 'w') as f:
            json.dump(self.data, f, indent=4, default=str)
    
    # --- GEMINI HELPER ---
    def ask_gemini(self, prompt):
        if not self.model: 
            return None
        try:
            response = self.model.generate_content(prompt)
            if not response.parts:
                return "⚠️ AI Response Blocked (Safety)"
            return response.text.strip()
        except Exception as e:
            self.last_error = str(e)
            return None

    # --- FEATURE: LAZY LEARNING EXPIRY ---
    def get_ai_expiry(self, item_name):
        if not self.model: return (7, "Default (No AI)")
        
        prompt = (
            f"Analyze '{item_name}'. 1. Is it perishable food? "
            "2. If NO (electronics, furniture, nonsense, or non-food like 'cement'), return -1. "
            "3. If YES, return average fridge shelf life in days. "
            "Return ONLY the integer."
        )
        res = self.ask_gemini(prompt)
        
        if not res or "⚠️" in res:
            return (7, "Default (AI Error)")

        nums = re.findall(r'-?\d+', res)
        if nums: 
            return (int(nums[0]), "Gemini AI")
            
        return (7, "Default (Parse Error)")

    def record_purchase(self, item, quantity=1):
        item = item.strip().lower()
        today = datetime.now().strftime("%Y-%m-%d")
        
        if item in self.expiry_map:
            days = self.expiry_map[item]
            source = "Memory"
        else:
            days, status = self.get_ai_expiry(item)
            
            if "Gemini AI" in status and days > 0:
                self.data["learned_expiry"][item] = days
                self.expiry_map[item] = days
                source = "Gemini AI"
            else:
                source = status 
        
        if days <= 0:
            expiry_date = "N/A (Non-perishable)"
            disp_days = "Infinite"
        else:
            expiry_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
            disp_days = f"{days} days"
        
        self.data["purchase_history"].append({
            "item": item, "quantity": quantity, "purchase_date": today,
            "expiry_date": expiry_date, "expiry_source": source
        })
        self.data["last_purchase"][item] = today
        if item in self.data["grocery_list"]: self.data["grocery_list"].remove(item)
        self.save_data()
        
        return f"🛍️ Purchased {quantity}x {item.title()} (Expires: {disp_days} via {source})"

    def check_dietary_safety(self, item):
        user_diet = self.data["user_preferences"].get("diet", "None")
        if user_diet == "None": return None
        prompt = f"I follow a {user_diet} diet. Is '{item}' allowed? Answer 'YES' or 'NO' followed by a 5 word reason."
        return self.ask_gemini(prompt)

    def add_item(self, item):
        item = item.strip().lower()
        if not item: return "❌ Enter name"
        if item in self.data["grocery_list"]: return f"⚠️ Already on list!"
        
        warnings = ""
        ai_thought = ""

        if self.use_llm and self.model:
            diet_check = self.check_dietary_safety(item)
            if diet_check and "NO" in diet_check.upper():
                warnings = f"\n\n🚨 **Dietary Warning:** {diet_check}"
            elif diet_check is None and self.last_error:
                 warnings = f"\n\n⚠️ **AI Error:** Could not check diet."
            
            ai_thought = self.ask_gemini(f"Should I add {item} to a grocery list? Answer in 1 short sentence.")
            if not ai_thought: ai_thought = "⚠️ AI Unavailable."
        else:
            ai_thought = "🤖 Using rule-based reasoning..."
        
        self.data["grocery_list"].append(item)
        self.save_data()
        
        suggestions = []
        if item in self.item_pairings:
            suggestions.append(f"**Pairs well with:** {', '.join(self.item_pairings[item])}")
        
        return f"✅ Added {item.title()}!\n\n**AI Analysis:** {ai_thought}{warnings}\n\n" + "\n".join(suggestions)

    def generate_recipes(self):
        if not self.model: return "⚠️ Enable AI first."
        ingredients = self.data['grocery_list'] + [p['item'] for p in self.data['purchase_history'][-10:]]
        if not ingredients: return "Kitchen empty!"
        
        prompt = f"I have: {', '.join(set(ingredients))}. Suggest 3 simple recipes. Format with emojis."
        res = self.ask_gemini(prompt)
        return res if res else f"⚠️ AI Error: {self.last_error}"

    def categorize_list(self):
        if not self.data['grocery_list']: return "List empty."
        prompt = f"Sort these into store aisles (Produce, Dairy, etc): {', '.join(self.data['grocery_list'])}. Return a clean list."
        res = self.ask_gemini(prompt)
        return res if res else f"⚠️ AI Error: {self.last_error}"

    def check_restock_needs(self):
        suggs = []
        today = datetime.now()
        for item, last in self.data["last_purchase"].items():
            if item in self.data["grocery_list"]: continue
            try:
                days = (today - datetime.strptime(last, "%Y-%m-%d")).days
                freq = self.expiry_map.get(item, 7)
                if days >= freq: suggs.append(f"🔄 **{item.title()}**: Bought {days} days ago.")
            except: continue
        return suggs

    def get_expiry_alerts(self):
        alerts = []
        today = datetime.now()
        for p in self.data["purchase_history"]:
            if "expiry_date" in p and p["expiry_date"] != "N/A (Non-perishable)":
                try:
                    left = (datetime.strptime(p["expiry_date"], "%Y-%m-%d") - today).days
                    if left < 0 and left > -30: alerts.append(f"❌ **{p['item']}** expired!")
                    elif 0 <= left <= 2: alerts.append(f"⚠️ **{p['item']}** expires soon!")
                except: continue
        return alerts

# ========== STREAMLIT APP ==========
def main():
    st.set_page_config(page_title="Smart Grocery AI", page_icon="🛒", layout="wide")
    st.markdown("""<style>.main-header {font-size: 2.5rem; color: #2E86AB; text-align: center;} 
    .stButton>button {width: 100%; border-radius: 10px;}</style>""", unsafe_allow_html=True)
    st.markdown("<h1 class='main-header'>🤖 AI Grocery Assistant</h1>", unsafe_allow_html=True)
    
    # --- SETUP ---
    env_key = os.environ.get("GOOGLE_API_KEY", "")
    with st.sidebar:
        st.header("⚙️ Settings")
        api_key = env_key if env_key else st.text_input("Gemini API Key:", type="password")
        
        if env_key: 
            st.success("✅ API Key Loaded from .env")
        elif api_key:
            st.success("✅ API Key Entered")
        
        use_llm = st.checkbox("Enable AI Features", value=bool(api_key))
        
        # --- CONNECTION TESTER ---
        if use_llm:
            if st.button("📡 Test AI Connection"):
                if 'assistant' in st.session_state:
                    assistant = st.session_state.assistant
                    if assistant.model:
                        with st.spinner(f"Testing {assistant.model_name}..."):
                            test_res = assistant.ask_gemini("Say 'Hello' in 1 word.")
                            if test_res and "⚠️" not in test_res:
                                st.success(f"Connected to {assistant.model_name}!")
                            else:
                                st.error(f"Failed: {assistant.last_error}")
                    else:
                         st.error(f"No Model Found: {assistant.last_error}")
                else:
                    st.warning("Initialize app first.")

        st.divider()
        st.subheader("🥗 Dietary Restrictions")
        current_diet = st.session_state.get('assistant', None).data["user_preferences"].get("diet", "None") if 'assistant' in st.session_state else "None"
        diet_choice = st.selectbox("I am:", ["None", "Vegan", "Vegetarian", "Gluten-Free", "Halal"], index=["None", "Vegan", "Vegetarian", "Gluten-Free", "Halal"].index(current_diet) if current_diet in ["None", "Vegan", "Vegetarian", "Gluten-Free", "Halal"] else 0)
        
        if st.button("💾 Save Diet"):
            if 'assistant' in st.session_state:
                st.session_state.assistant.data["user_preferences"]["diet"] = diet_choice
                st.session_state.assistant.save_data()
                st.success(f"Saved: {diet_choice}")

        st.divider()
        if st.button("🔄 Reset System"):
            if 'assistant' in st.session_state:
                st.session_state.assistant.data = st.session_state.assistant.default_data()
                st.session_state.assistant.save_data()
                st.rerun()

    if 'assistant' not in st.session_state:
        st.session_state.assistant = GroceryAssistant(use_llm=use_llm, api_key=api_key)
    
    # Refresh settings
    st.session_state.assistant.use_llm = use_llm
    st.session_state.assistant.api_key = api_key
    # Re-trigger setup if key changes
    if use_llm and api_key and not st.session_state.assistant.model:
        st.session_state.assistant = GroceryAssistant(use_llm=use_llm, api_key=api_key)

    # --- ERROR DISPLAY ---
    if st.session_state.assistant.last_error:
        st.error(f"🛑 AI Error: {st.session_state.assistant.last_error}")
        st.caption("Common fixes: Run 'pip install --upgrade google-generativeai', check Key quota, or restart app.")
        if st.button("Clear Error"):
            st.session_state.assistant.last_error = None
            st.rerun()

    col1, col2 = st.columns([2, 1])

    with col1:
        st.header("📢 Smart Predictions")
        suggs = st.session_state.assistant.check_restock_needs()
        if suggs:
            for s in suggs:
                c1, c2 = st.columns([4,1])
                c1.info(s)
                if c2.button("Add", key=s): 
                    st.session_state.assistant.add_item(s.split("**")[1])
                    st.rerun()
        else: st.caption("✅ No restocks needed.")
        
        st.divider()
        st.header("📝 Add Items")
        with st.form("add"):
            new_item = st.text_input("Item:")
            if st.form_submit_button("➕ Add"):
                res = st.session_state.assistant.add_item(new_item)
                st.info(res)
        
        st.divider()
        st.header("👨‍🍳 AI Kitchen")
        ac1, ac2 = st.columns(2)
        with ac1:
            if st.button("🥦 Categorize List"):
                with st.spinner("Sorting..."):
                    st.info(st.session_state.assistant.categorize_list())
        with ac2:
            if st.button("🍳 Suggest Recipes"):
                with st.spinner("Cooking ideas..."):
                    st.success(st.session_state.assistant.generate_recipes())

        st.header(f"📋 List ({len(st.session_state.assistant.data['grocery_list'])})")
        for i, item in enumerate(st.session_state.assistant.data["grocery_list"], 1):
            with st.expander(f"{i}. {item.title()}"):
                if st.button("Remove", key=f"del_{item}"):
                    st.session_state.assistant.data["grocery_list"].remove(item)
                    st.session_state.assistant.save_data()
                    st.rerun()

    with col2:
        st.header("🛍️ Record Purchase")
        with st.form("rec"):
            p_item = st.text_input("Item:")
            p_qty = st.number_input("Qty:", 1)
            if st.form_submit_button("✓ Record"):
                with st.spinner("🧠 AI Checking..."):
                    res = st.session_state.assistant.record_purchase(p_item, p_qty)
                    st.session_state['last_msg'] = res
                    st.rerun()
        
        if 'last_msg' in st.session_state:
            st.success(st.session_state['last_msg'])
            del st.session_state['last_msg']

        st.subheader("📅 Expiry Alerts")
        alerts = st.session_state.assistant.get_expiry_alerts()
        if alerts: 
            for a in alerts: st.warning(a)
        else: st.success("No expirations soon.")

    st.divider()
    with st.expander("📦 Full Inventory", expanded=True):
        hist = st.session_state.assistant.data["purchase_history"]
        if hist:
            df = pd.DataFrame(hist)[["item", "quantity", "purchase_date", "expiry_date", "expiry_source"]]
            st.dataframe(df, use_container_width=True)
        else: st.info("Inventory empty.")

if __name__ == "__main__":
    main()