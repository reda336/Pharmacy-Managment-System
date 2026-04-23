
# Digital Pharmacy Management System
### 📝 Project Overview
The Digital Pharmacy Management System is an integrated technical solution designed to bridge the gap between pharmacies and user needs. It provides a seamless digital environment for medication search, order tracking, and stock management, ensuring a secure and documented experience for both pharmacists and customers.
### 🚀 Key Features
#### 1. Seamless User Experience
 * **Digital Browsing & Ordering:** Users can easily browse available medications, add them to a shopping cart, and provide contact details for precise delivery.
 * **Real-Time Order Tracking:** Through a dedicated tracking page, users can monitor their order status (Processing or Ready for Pickup) using their phone number.
 * **Digital Invoicing:** Once an order is ready, the system generates a professional **PDF** invoice to ensure documentation and user rights.
#### 2. Smart "Procurement Requests" (Nawaqis)
 * **Securing Out-of-Stock Items:** When a medication is unavailable, the system opens a specific "Procurement Request" for the user.
 * **Instant Pharmacist Alerts:** Pharmacists receive real-time notifications on their dashboard with details of the missing medication and client contact info.
 * **Sales Optimization:** Pharmacists can contact customers as soon as the medication becomes available, converting missed opportunities into successful sales.
#### 3. Technical Advantages for Pharmacists
 * **Digital Archiving:** The system replaces traditional paperwork by digitally organizing all sales and procurement requests for easy retrieval.
 * **Verified Environment:** To maintain high reliability, the system only grants access to pharmacies licensed by the administration.
### 🛠 Tech Stack
 * **Backend Framework:** Flask (Python)
 * **Database Management:**
   * **PostgreSQL:** Utilized for production environments (e.g., Render).
   * **SQLite:** Used as a local database for rapid development and testing.
 * **ORM:** SQLAlchemy for efficient and secure database operations.
 * **Frontend:** HTML5, CSS3, and JavaScript for a responsive user interface.
### ⚙️ Advanced Deployment Logic
The codebase is optimized for stability on cloud platforms:
 * **Dynamic URI Handling:** The system automatically converts postgres:// to postgresql:// to ensure compatibility with modern SQLAlchemy versions.
 * **Automatic Fallback:** A built-in logic check ensures that if an external database connection is unavailable, the system automatically fails over to the local pharmacy.db SQLite file to prevent downtime.
### 📂 Core Repository Structure
 * app.py: The primary application file managing routes and core logic.
 * models.py: Defines the database schema (Medications, Orders, Pharmacy Profiles).
 * templates/: Contains all UI components and frontend layouts.
 * requirements.txt: Lists all dependencies required to run the project.


