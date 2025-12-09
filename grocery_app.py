import streamlit as st
import json
from datetime import datetime, timedelta
import os
import pandas as pd
import time
import statistics

# ========== BACKEND LOGIC (RULE-BASED AGENT) ==========
class GroceryAssistant:
    def __init__(self):
        self.filename = "grocery_data.json"
        self.load_data()
        
        # --- RULE 1: SHELF LIFE (Used for Expiry & Default Restock) ---
        self.shelf_life_rules = {
            "milk": 7, "eggs": 14, "bread": 5, "cheese": 14,
            "yogurt": 7, "chicken": 3, "beef": 3, "fish": 2,
            "apples": 10, "bananas": 4, "default": 7
        }

        # --- RULE 2: HEALTHIER ALTERNATIVES (Recommendation System) ---
        # Emojis have been removed as requested.
        self.healthier_options = {
            "white bread": "Whole Wheat Bread",
            "soda": "Sparkling Water",
            "chips": "Popcorn",
            "crisps": "Nuts",
            "sugar": "Honey",
            "butter": "Olive Oil",
            "white rice": "Brown Rice",
        }
        
        # --- RULE 3: PAIRINGS (Additional Rule-based Suggestion) ---
        self.item_pairings = {
            "bread": ["Butter", "Jam"],
            "cereal": ["Milk"],
            "coffee": ["Milk", "Sugar"]
        }

    def default_data(self):
        return {
            "grocery_list": [], 
            "purchase_history": [],
            "last_purchase_date": {},
            "purchase_intervals": {} # Stores list of days between purchases for frequency learning
        }

    def load_data(self):
        """Loads data from file and gracefully handles missing keys for old data."""
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r') as f:
                    self.data = json.load(f)
            except:
                # Fallback if file is corrupted
                st.error("Corrupted data file found. Resetting data structure.")
                self.data = self.default_data()
        else:
            self.data = self.default_data()
            
        # Ensure new keys exist if loading old data structure (Fixes KeyError)
        if "last_purchase_date" not in self.data:
            self.data["last_purchase_date"] = {}
        if "purchase_intervals" not in self.data:
            self.data["purchase_intervals"] = {}
            
    
    def save_data(self):
        with open(self.filename, 'w') as f:
            json.dump(self.data, f, indent=4, default=str)

    # --- ENHANCEMENT 1: Calculate Average Frequency ---
    def calculate_average_interval(self, item):
        """Calculates the average number of days between purchases for an item."""
        if item in self.data["purchase_intervals"] and len(self.data["purchase_intervals"][item]) >= 1:
            return statistics.mean(self.data["purchase_intervals"][item])
        # Fallback to the default shelf life if not enough data
        return self.shelf_life_rules.get(item, self.shelf_life_rules["default"])

    def get_healthier_option(self, item):
        """Returns the healthy alternative name if one exists."""
        for unhealthy_key, alternative in self.healthier_options.items():
            if unhealthy_key in item.lower():
                return alternative
        return None

    def replace_item(self, old_item, new_item):
        """Swaps an unhealthy item for a healthy one in the list."""
        if old_item in self.data["grocery_list"]:
            index = self.data["grocery_list"].index(old_item)
            self.data["grocery_list"][index] = new_item
            self.save_data()
            return f"♻️ Swapped **{old_item}** for **{new_item}**!"
        return "⚠️ Item not found."

    def add_item(self, item):
        item = item.strip().lower()
        if not item: return "❌ Please enter an item name.", False
        if item in self.data["grocery_list"]: return f"⚠️ '{item.title()}' is already on your list!", False
        
        self.data["grocery_list"].append(item)
        self.save_data()
        
        feedback = [f"✅ Added **{item.title()}** to your list."]
        
        # [cite_start]Health Check (Simple Recommendation System) 
        alt = self.get_healthier_option(item)
        found_health_tip = False
        if alt:
            feedback.append(f"💡 **Health Tip:** Consider buying **{alt}** instead!")
            found_health_tip = True
            
        # [cite_start]Pairing Check (Rule-based reasoning) 
        for key, pairs in self.item_pairings.items():
            if key in item:
                feedback.append(f"🛒 **Don't forget:** {', '.join(pairs)}")
                break

        return "\n\n".join(feedback), found_health_tip

    def record_purchase(self, item, quantity=1):
        item = item.strip().lower() # The standardized purchase item name (e.g., 'olive oil')
        today = datetime.now()
        today_str = today.strftime("%Y-%m-%d")

        # 1. Update Purchase Interval History (for enhanced prediction)
        if item in self.data["last_purchase_date"]:
            last_date = datetime.strptime(self.data["last_purchase_date"][item], "%Y-%m-%d")
            days_passed = (today - last_date).days
            
            if item not in self.data["purchase_intervals"]:
                self.data["purchase_intervals"][item] = []
            
            # Record the interval only if it's reasonable (> 1 day)
            if days_passed > 1:
                self.data["purchase_intervals"][item].append(days_passed)

        # 2. Update Last Purchase Date
        self.data["last_purchase_date"][item] = today_str
        
        # 3. Calculate Expiry Date (Rule-based reminder)
        days_to_expire = self.shelf_life_rules.get(item, self.shelf_life_rules["default"])
        expiry_date = (today + timedelta(days=days_to_expire)).strftime("%Y-%m-%d")
        
        self.data["purchase_history"].append({
            "item": item, 
            "quantity": quantity, 
            "purchase_date": today_str,
            "expiry_date": expiry_date
        })
        
        # Robust List Removal Logic: find the item in the list even if there are slight mismatches
        # (e.g., list has 'olive oil' and user purchases 'Olive Oil')
        item_to_remove = None
        for listed_item in self.data["grocery_list"]:
            # Standardize comparison: check if purchased item is similar to the item on the list
            if item == listed_item.lower().strip():
                item_to_remove = listed_item
                break
                
        if item_to_remove:
            self.data["grocery_list"].remove(item_to_remove)
        
        self.save_data()
        return f"🛍️ Purchased {quantity}x {item.title()} (Expires on {expiry_date})"

    def predict_restock(self):
        """Predicts restock needs based on rule-based reasoning and historical frequency."""
        # [cite_start]Implementation requirement: Use rule-based reasoning to suggest items 
        suggestions = []
        today = datetime.now()
        
        for item, last_date_str in self.data["last_purchase_date"].items():
            # If item is already on the list, skip prediction
            if item in self.data["grocery_list"]: continue
            try:
                last_date = datetime.strptime(last_date_str, "%Y-%m-%d")
                days_passed = (today - last_date).days
                
                # Use the calculated average frequency (or default shelf life)
                avg_interval = self.calculate_average_interval(item)
                
                # Rule: Suggest restock if days passed is 90% or more of the expected interval
                threshold = avg_interval * 0.9 
                
                if days_passed >= threshold:
                    reason_type = f"Used up (Avg. {round(avg_interval)} days)"
                    if avg_interval == self.shelf_life_rules.get(item, 7):
                        reason_type = "Long time since last purchase (Default rule)"
                        
                    suggestions.append({
                        "item": item,
                        "days_ago": days_passed,
                        "reason": f"Bought {days_passed} days ago. {reason_type}."
                    })
            except: continue
        return suggestions

    def check_expiring_items(self):
        """Provides reminders for expiring items based on stored purchase history."""
        # [cite_start]Implementation requirement: Provide reminders for expiring items 
        alerts = []
        today = datetime.now()
        
        for idx, p in enumerate(self.data["purchase_history"]):
            if "expiry_date" in p:
                try:
                    expiry = datetime.strptime(p["expiry_date"], "%Y-%m-%d")
                    days_left = (expiry - today).days
                    
                    # Store a unique identifier (index) for removal
                    item_id = str(idx) 
                    
                    if days_left < 0:
                        alerts.append({
                            "type": "expired",
                            "item_id": item_id,
                            "msg": f"❌ **{p['item'].title()}** expired {abs(days_left)} days ago!"
                        })
                    elif 0 <= days_left <= 2:
                        alerts.append({
                            "type": "critical",
                            "item": p['item'],
                            "item_id": item_id,
                            "msg": f"⚠️ **{p['item'].title()}** expires in {days_left} days! Plan to use or restock."
                        })
                except: continue
        return alerts
    
    def remove_item_from_inventory(self, item_id_str):
        """Removes an item from the purchase history (inventory) by index."""
        try:
            item_id = int(item_id_str)
            # Remove the specific purchased instance
            del self.data["purchase_history"][item_id]
            self.save_data()
            return True
        except (IndexError, ValueError):
            return False

# ========== STREAMLIT UI ==========
def main():
    st.set_page_config(page_title="Rule-Based Grocery Agent", page_icon="🛒", layout="wide")
    
    # Custom CSS for styling
    st.markdown("""
    <style>
    .main-header { font-size: 2.5rem; color: #2E86AB; text-align: center; } 
    .stButton>button { border-radius: 8px; font-weight: bold;}
    .success-msg { background-color: #d4edda; padding: 15px; border-radius: 10px; color: #155724; border-left: 5px solid #28a745; margin-bottom: 10px;}
    .warning-msg { background-color: #fff3cd; padding: 15px; border-radius: 10px; color: #856404; border-left: 5px solid #ffeeba; margin-bottom: 10px;}
    .error-msg { background-color: #f8d7da; padding: 15px; border-radius: 10px; color: #721c24; border-left: 5px solid #dc3545; margin-bottom: 10px;}
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("<h1 class='main-header'>🛒 Smart Grocery Assistant</h1>", unsafe_allow_html=True)
   
    if 'assistant' not in st.session_state:
        st.session_state.assistant = GroceryAssistant()
    
    # --- Sidebar for controls ---
    with st.sidebar:
        st.header("⚙️ System Controls")
        if st.button("🔄 Reset All Data"):
            st.session_state.assistant.data = st.session_state.assistant.default_data()
            st.session_state.assistant.save_data()
            st.rerun()
        st.info("Agent Mode: Rule-Based (Enhanced Frequency Model)")

    col1, col2 = st.columns([2, 1])

    with col1:
        # [cite_start]1. Predictions (Missing Items) 
        st.subheader("📢 Restock Suggestions (AI Prediction)")
        predictions = st.session_state.assistant.predict_restock()
        if predictions:
            st.info(f"The assistant predicts you might need {len(predictions)} items:")
            for p in predictions:
                c1_p, c2_p = st.columns([4, 1])
                c1_p.write(f"**{p['item'].title()}** ({p['reason']})")
                if c2_p.button("Add", key=f"pred_{p['item']}"):
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

        # [cite_start]3. CURRENT LIST with Swap Buttons 
        st.write(f"**Current List ({len(st.session_state.assistant.data['grocery_list'])}):**")
        
        if st.session_state.assistant.data['grocery_list']:
            for item in list(st.session_state.assistant.data['grocery_list']):
                alt_option = st.session_state.assistant.get_healthier_option(item)
                
                if alt_option:
                    c_txt, c_swap, c_del = st.columns([2, 2, 1])
                else:
                    c_txt, c_del = st.columns([4, 1])
                
                c_txt.text(f"• {item.title()}")
                
                if alt_option:
                    # Only show the item name for the button label, not full string
                    alt_name_only = alt_option.split(' ')[0]
                    if c_swap.button(f"♻️ Swap for {alt_name_only}", key=f"swap_{item}"):
                        res = st.session_state.assistant.replace_item(item, alt_option)
                        st.toast(res)
                        time.sleep(0.5)
                        st.rerun()
                
                if c_del.button("❌", key=f"del_{item}"):
                    st.session_state.assistant.data["grocery_list"].remove(item)
                    st.session_state.assistant.save_data()
                    st.rerun()
        else:
            st.caption("Your list is empty. Add items above or record a purchase.")

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
        # [cite_start]5. Expiry Alerts 
        st.subheader("📅 Expiry Alerts (Inventory Check)")
        alerts = st.session_state.assistant.check_expiring_items()
        
        if alerts:
            for a in alerts:
                if a['type'] == 'expired':
                    c_err, c_del_inv = st.columns([3, 1])
                    c_err.markdown(f'<div class="error-msg">{a["msg"]}</div>', unsafe_allow_html=True)
                    if c_del_inv.button("🗑️ Remove", key=f"remove_exp_{a['item_id']}"):
                        st.session_state.assistant.remove_item_from_inventory(a['item_id'])
                        st.toast(f"Removed expired item.")
                        st.rerun()
                elif a['type'] == 'critical':
                    c_alert, c_btn = st.columns([3, 1])
                    c_alert.warning(a['msg'])
                    if c_btn.button("➕ Restock", key=f"restock_{a['item_id']}"):
                        st.session_state.assistant.add_item(a['item'])
                        st.toast(f"Added {a['item']} to list!")
                        st.rerun()
        else:
            st.success("All items in inventory are fresh! ✅")

    st.divider()
    with st.expander("📦 View Agent's Memory (History & Intervals)"):
        hist = st.session_state.assistant.data["purchase_history"]
        
        # Display Purchase History
        st.caption("Purchase History (Current Inventory):")
        if hist:
            df = pd.DataFrame(hist)
            # Re-index the DataFrame to match the item_id used for removal
            df.index = [str(i) for i in df.index] 
            st.table(df)
        else:
            st.info("No purchase history yet.")

        # Display Purchase Intervals (Learning)
        st.caption("Purchase Intervals (Agent's Learned Frequency):")
        if st.session_state.assistant.data["purchase_intervals"]:
            intervals_data = []
            for item, intervals in st.session_state.assistant.data["purchase_intervals"].items():
                intervals_data.append({
                    "Item": item.title(),
                    "Average Interval (Days)": round(statistics.mean(intervals), 1) if intervals else 'N/A',
                    "Total Intervals Recorded": len(intervals) 
                })
            st.table(pd.DataFrame(intervals_data))
        else:
            st.info("Need at least two purchases of an item to calculate a meaningful interval.")

if __name__ == "__main__":
    main()