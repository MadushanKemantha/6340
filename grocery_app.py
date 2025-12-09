import streamlit as st
import json
from datetime import datetime, timedelta
import os
import pandas as pd
import time

# ========== BACKEND LOGIC (RULE-BASED AGENT) ==========
class GroceryAssistant:
    def __init__(self):
        self.filename = "grocery_data.json"
        self.load_data()
        
        # --- RULE 1: SHELF LIFE ---
        self.shelf_life_rules = {
            "milk": 7, "eggs": 14, "bread": 5, "cheese": 14,
            "yogurt": 7, "chicken": 3, "beef": 3, "fish": 2,
            "rice": 30, "pasta": 30, "apples": 10, "bananas": 4,
            "shampoo": 30, "soap": 14, "toothpaste": 30,
            "default": 7
        }

        # --- RULE 2: HEALTHIER ALTERNATIVES ---
        self.healthier_options = {
            "white bread": "Whole Wheat Bread 🍞",
            "soda": "Sparkling Water 💧",
            "coke": "Sparkling Water 💧",
            "pepsi": "Sparkling Water 💧",
            "chips": "Popcorn 🍿",
            "crisps": "Nuts 🌰",
            "sugar": "Honey 🍯",
            "butter": "Olive Oil 🥑",
            "white rice": "Brown Rice 🍚",
            "chocolate": "Dark Chocolate 🍫",
            "ice cream": "Frozen Yogurt 🍨",
            "mayo": "Greek Yogurt 🥣",
            "candy": "Fresh Fruit 🍎",
            "cookies": "Oatmeal Cookies 🍪",
            "burger": "Turkey Burger 🍔",
            "pizza": "Cauliflower Pizza 🍕"
        }
        
        # --- RULE 3: PAIRINGS ---
        self.item_pairings = {
            "bread": ["Butter", "Jam"],
            "cereal": ["Milk"],
            "pasta": ["Pasta Sauce", "Cheese"],
            "eggs": ["Bread"],
            "pancakes": ["Syrup"],
            "coffee": ["Milk", "Sugar"]
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
            "grocery_list": [], 
            "purchase_history": [], 
            "last_purchase": {}
        }
    
    def save_data(self):
        with open(self.filename, 'w') as f:
            json.dump(self.data, f, indent=4, default=str)

    # --- HELPER: CHECK FOR ALTERNATIVE ---
    def get_healthier_option(self, item):
        """Returns the healthy alternative name if one exists."""
        for unhealthy_key, alternative in self.healthier_options.items():
            if unhealthy_key in item.lower():
                return alternative
        return None

    # --- FEATURE: REPLACE ITEM ---
    def replace_item(self, old_item, new_item):
        """Swaps an unhealthy item for a healthy one in the list."""
        if old_item in self.data["grocery_list"]:
            index = self.data["grocery_list"].index(old_item)
            self.data["grocery_list"][index] = new_item # Replace in place
            self.save_data()
            return f"♻️ Swapped **{old_item}** for **{new_item}**!"
        return "⚠️ Item not found."

    def add_item(self, item):
        item = item.strip().lower()
        if not item: return "❌ Please enter an item name."
        if item in self.data["grocery_list"]: return f"⚠️ '{item.title()}' is already on your list!"
        
        self.data["grocery_list"].append(item)
        self.save_data()
        
        feedback = [f"✅ Added **{item.title()}** to your list."]
        
        # Health Check
        alt = self.get_healthier_option(item)
        found_health_tip = False
        if alt:
            feedback.append(f"💡 **Health Tip:** Consider buying **{alt}** instead!")
            found_health_tip = True
            
        # Pairing Check
        for key, pairs in self.item_pairings.items():
            if key in item:
                feedback.append(f"🛒 **Don't forget:** {', '.join(pairs)}")
                break

        return "\n\n".join(feedback), found_health_tip

    def record_purchase(self, item, quantity=1):
        item = item.strip().lower()
        today = datetime.now()
        
        days_to_expire = 7 
        for key, days in self.shelf_life_rules.items():
            if key in item:
                days_to_expire = days
                break
        
        expiry_date = (today + timedelta(days=days_to_expire)).strftime("%Y-%m-%d")
        
        self.data["purchase_history"].append({
            "item": item, 
            "quantity": quantity, 
            "purchase_date": today.strftime("%Y-%m-%d"),
            "expiry_date": expiry_date
        })
        
        self.data["last_purchase"][item] = today.strftime("%Y-%m-%d")
        
        if item in self.data["grocery_list"]: 
            self.data["grocery_list"].remove(item)
        
        self.save_data()
        return f"🛍️ Purchased {quantity}x {item.title()} (Expires on {expiry_date})"

    def predict_restock(self):
        suggestions = []
        today = datetime.now()
        
        for item, last_date_str in self.data["last_purchase"].items():
            if item in self.data["grocery_list"]: continue
            try:
                last_date = datetime.strptime(last_date_str, "%Y-%m-%d")
                days_passed = (today - last_date).days
                
                expected_duration = 7
                for key, days in self.shelf_life_rules.items():
                    if key in item:
                        expected_duration = days
                        break
                
                if days_passed >= expected_duration:
                    suggestions.append({
                        "item": item,
                        "days_ago": days_passed,
                        "reason": f"Bought {days_passed} days ago"
                    })
            except: continue
        return suggestions

    def check_expiring_items(self):
        alerts = []
        today = datetime.now()
        
        for idx, p in enumerate(self.data["purchase_history"]):
            if "expiry_date" in p:
                try:
                    expiry = datetime.strptime(p["expiry_date"], "%Y-%m-%d")
                    days_left = (expiry - today).days
                    
                    if days_left < 0:
                        alerts.append({
                            "type": "expired",
                            "msg": f"❌ **{p['item'].title()}** expired {abs(days_left)} days ago!"
                        })
                    elif 0 <= days_left <= 2:
                        alerts.append({
                            "type": "critical",
                            "item": p['item'],
                            "id": idx,
                            "msg": f"⚠️ **{p['item'].title()}** expires in {days_left} days! Plan to use or restock."
                        })
                except: continue
        return alerts

# ========== STREAMLIT UI ==========
def main():
    st.set_page_config(page_title="Rule-Based Grocery Agent", page_icon="🛒", layout="wide")
    
    st.markdown("""
    <style>
    .main-header { font-size: 2.5rem; color: #2E86AB; text-align: center; } 
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold;}
    .success-msg { background-color: #d4edda; padding: 15px; border-radius: 10px; color: #155724; border-left: 5px solid #28a745; margin-bottom: 10px;}
    .warning-msg { background-color: #fff3cd; padding: 15px; border-radius: 10px; color: #856404; border-left: 5px solid #ffeeba; margin-bottom: 10px;}
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("<h1 class='main-header'>🛒 Smart Grocery Assistant</h1>", unsafe_allow_html=True)
   
    
    if 'assistant' not in st.session_state:
        st.session_state.assistant = GroceryAssistant()
    
    with st.sidebar:
        st.header("⚙️ System Controls")
        if st.button("🔄 Reset All Data"):
            st.session_state.assistant.data = st.session_state.assistant.default_data()
            st.session_state.assistant.save_data()
            st.rerun()
        st.info("System Mode: Rule-Based (Offline)")

    col1, col2 = st.columns([2, 1])

    with col1:
        # 1. Predictions
        st.subheader("📢 Restock Suggestions")
        predictions = st.session_state.assistant.predict_restock()
        if predictions:
            st.info(f"You might be running low on {len(predictions)} items:")
            for p in predictions:
                c1, c2 = st.columns([4, 1])
                c1.write(f"**{p['item'].title()}** ({p['reason']})")
                if c2.button("Add", key=f"pred_{p['item']}"):
                    st.session_state.assistant.add_item(p['item'])
                    st.rerun()
        else:
            st.success("✅ No restock suggestions.")
            
        st.divider()

        # 2. Add Items
        st.subheader("📝 Manage Grocery List")
        with st.form("add_form"):
            new_item = st.text_input("Enter item name (e.g., 'Chips', 'Coke'):")
            submitted = st.form_submit_button("➕ Add to List")
            
            if submitted and new_item:
                result_text, is_health_warning = st.session_state.assistant.add_item(new_item)
                if is_health_warning:
                    st.markdown(f'<div class="warning-msg">{result_text.replace(chr(10), "<br>")}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="success-msg">{result_text.replace(chr(10), "<br>")}</div>', unsafe_allow_html=True)

        # 3. CURRENT LIST WITH SWAP BUTTONS
        st.write(f"**Current List ({len(st.session_state.assistant.data['grocery_list'])}):**")
        
        if st.session_state.assistant.data['grocery_list']:
            for item in st.session_state.assistant.data['grocery_list']:
                # Check if this item has a healthier alternative
                alt_option = st.session_state.assistant.get_healthier_option(item)
                
                # Layout: Item Name | Swap Button (if unhealthy) | Delete Button
                if alt_option:
                    c_txt, c_swap, c_del = st.columns([2, 2, 1])
                else:
                    c_txt, c_del = st.columns([4, 1])
                
                c_txt.text(f"• {item.title()}")
                
                # If unhealthy, show Swap Button
                if alt_option:
                    if c_swap.button(f"♻️ Swap for {alt_option.split(' ')[0]}", key=f"swap_{item}"):
                        res = st.session_state.assistant.replace_item(item, alt_option)
                        st.toast(res)
                        time.sleep(0.5)
                        st.rerun()
                
                if c_del.button("❌", key=f"del_{item}"):
                    st.session_state.assistant.data["grocery_list"].remove(item)
                    st.session_state.assistant.save_data()
                    st.rerun()
        else:
            st.caption("Your list is empty.")

    with col2:
        # 4. Record Purchase
        st.subheader("🛍️ Record Purchase")
        with st.form("buy_form"):
            buy_item = st.text_input("Item Purchased:")
            buy_qty = st.number_input("Quantity:", 1)
            if st.form_submit_button("✓ Confirm Purchase"):
                if buy_item:
                    res = st.session_state.assistant.record_purchase(buy_item, buy_qty)
                    st.success(res)
                    time.sleep(1)
                    st.rerun()

        st.divider()
        # 5. Expiry Alerts
        st.subheader("📅 Expiry Alerts")
        alerts = st.session_state.assistant.check_expiring_items()
        
        if alerts:
            for a in alerts:
                if a['type'] == 'expired':
                    st.error(a['msg'])
                elif a['type'] == 'critical':
                    c_alert, c_btn = st.columns([3, 1])
                    c_alert.warning(a['msg'])
                    if c_btn.button("➕ Restock", key=f"restock_{a['id']}"):
                        st.session_state.assistant.add_item(a['item'])
                        st.toast(f"Added {a['item']} to list!")
                        st.rerun()
        else:
            st.success("All items are fresh! ✅")

    st.divider()
    with st.expander("📦 View Full Purchase History"):
        hist = st.session_state.assistant.data["purchase_history"]
        if hist:
            df = pd.DataFrame(hist)
            st.table(df)
        else:
            st.info("No purchase history yet.")

if __name__ == "__main__":
    main()