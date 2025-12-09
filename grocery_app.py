import streamlit as st
import json
from datetime import datetime, timedelta
import os
import requests
import time
import random
from dotenv import load_dotenv

load_dotenv()

# ========== BACKEND ASSISTANT CLASS ==========
class GroceryAssistant:
    def __init__(self, use_llm=False, api_key=""):
        self.filename = "grocery_data.json"
        self.use_llm = use_llm
        self.api_key = api_key
        self.load_data()
        
        # Healthier alternatives mapping
        self.healthier_options = {
            "white bread": "whole wheat bread 🍞",
            "soda": "sparkling water or herbal tea 💧",
            "chips": "air-popped popcorn or nuts 🌰",
            "sugar": "honey or stevia 🍯",
            "butter": "olive oil or avocado spread 🥑",
            "white rice": "brown rice or quinoa 🍚",
            "milk chocolate": "dark chocolate (70%+) 🍫",
            "ice cream": "frozen yogurt or fruit sorbet 🍨",
            "potato": "sweet potato or cauliflower 🥦",
            "mayonnaise": "greek yogurt or hummus 🥣"
        }
        
        # Common item pairings
        self.item_pairings = {
            "bread": ["butter", "jam", "cheese", "peanut butter"],
            "coffee": ["milk", "sugar", "cream", "cookies"],
            "pasta": ["pasta sauce", "cheese", "garlic", "olive oil"],
            "eggs": ["milk", "bread", "butter", "cheese"],
            "cereal": ["milk", "yogurt", "bananas", "berries"],
            "tea": ["honey", "milk", "lemon", "biscuits"],
            "pancake": ["syrup", "butter", "berries", "whipped cream"],
            "burger": ["buns", "cheese", "lettuce", "tomato"],
            "pizza": ["cheese", "tomato sauce", "pepperoni", "mushrooms"]
        }
        
        # Expiry days
        self.expiry_days = {
            "milk": 7, "eggs": 14, "bread": 5, "cheese": 10,
            "yogurt": 10, "meat": 3, "fish": 2, "vegetables": 7,
            "fruits": 5, "default": 7
        }
    
    def load_data(self):
        """Load data from JSON file"""
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r') as f:
                    self.data = json.load(f)
            except:
                self.data = self.default_data()
        else:
            self.data = self.default_data()
    
    def default_data(self):
        """Default data structure"""
        return {
            "grocery_list": [],
            "purchase_history": [],
            "last_purchase": {},
            "user_preferences": {
                "health_conscious": True,
                "budget": "medium",
                "dietary_restrictions": [],
                "family_size": 1
            },
            "shopping_frequency": "weekly"
        }
    
    def save_data(self):
        """Save data to JSON file"""
        with open(self.filename, 'w') as f:
            json.dump(self.data, f, indent=4, default=str)
    
    def ask_ai(self, prompt):
        """Get AI response"""
        if not self.use_llm or not self.api_key:
            return self.simulate_ai_response()
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "gpt-3.5-turbo",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 100
        }
        
        try:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=5
            )
            
            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"].strip()
            else:
                return self.simulate_ai_response()
                
        except:
            return self.simulate_ai_response()
    
    def simulate_ai_response(self):
        """Simulate AI when API is unavailable"""
        responses = [
            "Based on your shopping habits, this seems like a good addition.",
            "Consider if you already have this item at home.",
            "This pairs well with items on your list!",
            "There might be a healthier alternative available.",
            "You bought this recently. Do you need more?"
        ]
        return random.choice(responses)
    
    def add_item(self, item):
        """Add item to list"""
        item = item.strip().lower()
        
        if not item:
            return "❌ Please enter an item name"
        
        if item in self.data["grocery_list"]:
            return f"⚠️ {item.title()} is already on your list!"
        
        # AI reasoning
        if self.use_llm:
            ai_thought = self.ask_ai(f"Should I add {item} to grocery list? List: {self.data['grocery_list']}")
        else:
            ai_thought = "🤖 Using rule-based reasoning..."
        
        # Add item
        self.data["grocery_list"].append(item)
        self.save_data()
        
        # Generate suggestions
        suggestions = []
        if item in self.item_pairings:
            suggestions.append(f"**Pairs well with:** {', '.join(self.item_pairings[item])}")
        
        if item in self.healthier_options:
            suggestions.append(f"**Healthier option:** {self.healthier_options[item]}")
        
        if item in self.data["last_purchase"]:
            last_date = datetime.strptime(self.data["last_purchase"][item], "%Y-%m-%d")
            days_since = (datetime.now() - last_date).days
            if days_since < 7:
                suggestions.append(f"**Note:** Bought {days_since} days ago")
        
        return f"✅ Added {item.title()}!\n\n**AI Analysis:** {ai_thought}\n\n" + "\n".join(suggestions)
    
    def record_purchase(self, item, quantity=1):
        """Record a purchase"""
        item = item.strip().lower()
        today = datetime.now().strftime("%Y-%m-%d")
        expiry_days = self.expiry_days.get(item, self.expiry_days["default"])
        expiry_date = (datetime.now() + timedelta(days=expiry_days)).strftime("%Y-%m-%d")
        
        self.data["purchase_history"].append({
            "item": item,
            "quantity": quantity,
            "purchase_date": today,
            "expiry_date": expiry_date
        })
        
        self.data["last_purchase"][item] = today
        
        # Remove from grocery list if present
        if item in self.data["grocery_list"]:
            self.data["grocery_list"].remove(item)
        
        self.save_data()
        return f"🛍️ Purchased {quantity}x {item.title()} (expires: {expiry_date})"
    
    def get_expiry_alerts(self):
        """Get expiring items"""
        today = datetime.now()
        alerts = []
        
        for purchase in self.data["purchase_history"]:
            if "expiry_date" in purchase:
                expiry_date = datetime.strptime(purchase["expiry_date"], "%Y-%m-%d")
                days_left = (expiry_date - today).days
                
                if days_left < 0:
                    alerts.append(f"❌ **{purchase['item'].title()}** - EXPIRED {abs(days_left)} days ago!")
                elif days_left <= 2:
                    alerts.append(f"⚠️ **{purchase['item'].title()}** - Expires in {days_left} day(s)")
        
        return alerts
    
    def get_shopping_tips(self):
        """Generate shopping tips"""
        if self.use_llm and self.api_key:
            prompt = f"Give 3 shopping tips for this list: {self.data['grocery_list']}"
            return self.ask_ai(prompt)
        else:
            tips = [
                "🛒 **Shop with a list** to avoid impulse buys",
                "💰 **Buy in bulk** for frequently used items",
                "🥦 **Choose seasonal produce** for better prices",
                "📅 **Check expiry dates** before purchasing",
                "🌱 **Consider plant-based alternatives** for health",
                "🧊 **Freeze items** that spoil quickly",
                "📊 **Track spending** to stay within budget"
            ]
            return "\n".join(random.sample(tips, 3))

# ========== STREAMLIT APP ==========
def main():
    # Page configuration
    st.set_page_config(
        page_title="AI Grocery Assistant 🤖",
        page_icon="🛒",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Custom CSS
    st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        color: #2E86AB;
        text-align: center;
        margin-bottom: 2rem;
    }
    .stButton>button {
        background-color: #2E86AB;
        color: white;
        font-weight: bold;
        border-radius: 10px;
        padding: 10px 20px;
        border: none;
    }
    .stButton>button:hover {
        background-color: #1B5E8E;
    }
    .success-box {
        background-color: #DFF0D8;
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid #3C763D;
        margin: 10px 0;
    }
    .warning-box {
        background-color: #FCF8E3;
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid #8A6D3B;
        margin: 10px 0;
    }
    .info-box {
        background-color: #D9EDF7;
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid #31708F;
        margin: 10px 0;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Title
    st.markdown("<h1 class='main-header'>🤖 AI Grocery Shopping Assistant</h1>", unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Settings")
        
        # API Key input
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            api_key = st.text_input("OpenAI API Key (optional):", type="password")
            st.caption("Leave empty for simulated AI")
        
        use_llm = st.checkbox("Enable AI Reasoning", value=bool(api_key))
        
        st.divider()
        
        # Quick actions
        st.header("🚀 Quick Actions")
        
        if st.button("🔄 Reset Data"):
            if st.session_state.get('assistant'):
                st.session_state.assistant.data = st.session_state.assistant.default_data()
                st.session_state.assistant.save_data()
                st.success("Data reset!")
                st.rerun()
        
        st.divider()
        
        # Info
        st.header("ℹ️ About")
        st.info("""
        This AI assistant helps you:
        - 🛒 Manage grocery lists
        - 🧠 Suggest items using AI
        - 🥗 Recommend healthier options
        - 📅 Track expiry dates
        """)
    
    # Initialize assistant in session state
    if 'assistant' not in st.session_state:
        st.session_state.assistant = GroceryAssistant(use_llm=use_llm, api_key=api_key)
    
    # Update assistant settings
    st.session_state.assistant.use_llm = use_llm
    st.session_state.assistant.api_key = api_key
    
    # Main layout
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("📝 Add Items")
        
        # Add item form
        with st.form("add_item_form"):
            item_input = st.text_input("Item name:", placeholder="e.g., milk, bread, eggs...")
            col_a, col_b = st.columns(2)
            with col_a:
                submit = st.form_submit_button("➕ Add Item", type="primary")
            with col_b:
                quick_add = st.form_submit_button("🎯 Quick Add Sample")
        
        if submit and item_input:
            result = st.session_state.assistant.add_item(item_input)
            st.markdown(f'<div class="success-box">{result}</div>', unsafe_allow_html=True)
            st.rerun()
        
        if quick_add:
            sample_items = ["Milk", "Bread", "Eggs", "Cheese", "Fruits"]
            for item in sample_items:
                st.session_state.assistant.add_item(item)
            st.success(f"Added {len(sample_items)} sample items!")
            st.rerun()
        
        st.divider()
        
        # Grocery list
        st.header(f"📋 Your List ({len(st.session_state.assistant.data['grocery_list'])} items)")
        
        if not st.session_state.assistant.data["grocery_list"]:
            st.info("Your list is empty. Add some items above!")
        else:
            for i, item in enumerate(st.session_state.assistant.data["grocery_list"], 1):
                with st.expander(f"{i}. {item.title()}"):
                    # Show suggestions for this item
                    if item in st.session_state.assistant.healthier_options:
                        st.info(f"🥗 **Healthier option:** {st.session_state.assistant.healthier_options[item]}")
                    
                    if item in st.session_state.assistant.item_pairings:
                        st.success(f"🤝 **Pairs with:** {', '.join(st.session_state.assistant.item_pairings[item][:3])}")
                    
                    # Remove button
                    if st.button(f"Remove {item}", key=f"remove_{item}"):
                        st.session_state.assistant.data["grocery_list"].remove(item)
                        st.session_state.assistant.save_data()
                        st.success(f"Removed {item}")
                        st.rerun()
        
        # Clear all button
        if st.session_state.assistant.data["grocery_list"]:
            if st.button("🗑️ Clear All Items", type="secondary"):
                st.session_state.assistant.data["grocery_list"] = []
                st.session_state.assistant.save_data()
                st.success("All items cleared!")
                st.rerun()
    
    with col2:
        st.header("🎯 Smart Features")
        
        # Record purchase
        st.subheader("🛍️ Record Purchase")
        with st.form("purchase_form"):
            purchase_item = st.text_input("Purchased item:")
            purchase_qty = st.number_input("Quantity:", min_value=1, value=1)
            if st.form_submit_button("✓ Record Purchase"):
                if purchase_item:
                    result = st.session_state.assistant.record_purchase(purchase_item, purchase_qty)
                    st.success(result)
                    st.rerun()
        
        st.divider()
        
        # Expiry alerts
        st.subheader("📅 Expiry Alerts")
        alerts = st.session_state.assistant.get_expiry_alerts()
        if alerts:
            for alert in alerts:
                if "❌" in alert:
                    st.error(alert)
                else:
                    st.warning(alert)
        else:
            st.success("✅ No items expiring soon!")
        
        st.divider()
        
        # Shopping tips
        st.subheader("💡 AI Shopping Tips")
        if st.button("Get Smart Tips"):
            with st.spinner("🤖 AI is thinking..."):
                time.sleep(1)  # Simulate thinking
                tips = st.session_state.assistant.get_shopping_tips()
                st.markdown(f'<div class="info-box">{tips}</div>', unsafe_allow_html=True)
        
        st.divider()
        
        # Demo mode
        st.subheader("🎬 Demo Mode")
        if st.button("Run AI Demo"):
            with st.spinner("Running AI demonstration..."):
                demo_results = []
                
                # Step 1: Add demo items
                demo_items = ["milk", "white bread", "eggs", "soda"]
                for item in demo_items:
                    time.sleep(0.5)
                    result = st.session_state.assistant.add_item(item)
                    demo_results.append(f"Added: {item.title()}")
                
                # Step 2: Record purchases
                st.session_state.assistant.record_purchase("milk", 2)
                demo_results.append("Purchased: Milk")
                
                # Step 3: Show tips
                tips = st.session_state.assistant.get_shopping_tips()
                demo_results.append("Generated AI tips")
                
                st.success("Demo completed!")
                st.write("**What happened:**")
                for step in demo_results:
                    st.write(f"✓ {step}")
                
                st.markdown(f'<div class="info-box">{tips}</div>', unsafe_allow_html=True)
    
    # Footer
    st.divider()
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        st.caption(f"🤖 AI Mode: {'Enabled ✅' if use_llm and api_key else 'Simulated 🔄'}")
    with col_f2:
        st.caption(f"📊 Items in list: {len(st.session_state.assistant.data['grocery_list'])}")
    with col_f3:
        st.caption("Made for EEX7340/EEX6340 Mini Project")

# ========== RUN THE APP ==========
if __name__ == "__main__":
    main()