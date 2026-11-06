# DineFlow — QR Restaurant Ordering System (BCA project starter)

A local-first demo with:
- Customer menu opened using a table-specific QR code
- Cart and order placement
- Live manager dashboard (Socket.IO)
- Kitchen display
- Order status updates
- Basic menu availability management
- Table QR code generation (Tables 1–10)
- SQLite database created automatically

## 1. Requirements
- Windows 10/11
- Python 3.10 or newer
- Internet connection for the Google Fonts, sample food photos and Socket.IO browser CDN (the core app runs locally)

## 2. Run on Windows
1. Extract the ZIP file.
2. Open the extracted `qr_restaurant_system` folder.
3. In the folder address bar, type `cmd` and press Enter.
4. Create a virtual environment:

   `py -m venv venv`

5. Activate it:

   `venv\\Scripts\\activate`

6. Install packages:

   `python -m pip install -r requirements.txt`

7. Start the app:

   `python app.py`

8. Open `http://127.0.0.1:5000` in your browser.

The SQLite database `restaurant.db` is created automatically on first run.

## 3. Demo pages
- Home: `http://127.0.0.1:5000/`
- Customer table 1: `http://127.0.0.1:5000/menu/1`
- Manager login: `http://127.0.0.1:5000/manager/login`
- Kitchen screen: `http://127.0.0.1:5000/kitchen`

Demo manager credentials:
- Username: `admin`
- Password: `admin123`

Change these before any public use:
- Set environment variables `MANAGER_USERNAME`, `MANAGER_PASSWORD`, and `SECRET_KEY`.
- Do not deploy with the demo credentials or Flask debug mode enabled.

## 4. Test the QR order flow locally
1. Open the customer menu in one browser tab.
2. Open the manager dashboard in another tab and log in.
3. Add items to the cart on the customer page and place an order.
4. The order should appear in the manager dashboard without refreshing.
5. Open the kitchen screen to view active orders and update their status.

For testing on two devices on the same Wi-Fi, use your computer's local IPv4 address instead of `127.0.0.1`, and allow Python through Windows Firewall if prompted. Both devices must be on the same network.

## 5. QR code generation
After manager login, select **Table QR Codes**. The app generates QR codes for tables 1–10.
- Local testing: generated QR codes point to the host used to open the QR page.
- Public deployment: set `PUBLIC_BASE_URL` to your deployed HTTPS address before generating QR codes. Example: `https://your-restaurant-domain.com`.

## 6. Important project limitations / next improvements
This is a learning MVP, not a production-ready restaurant POS. Before real restaurant use, add:
- Proper hashed staff passwords and role-based access
- CSRF protection, rate limiting, input validation and secure deployment settings
- Secure table-session tokens / signed QR links to prevent table-number tampering
- Payment gateway integration and verified payment callbacks
- GST/tax configuration reviewed for the restaurant's actual requirements
- Order cancellation/refund rules and audit logs
- Backups, HTTPS, monitoring and privacy policy
- Kitchen-specific user accounts and permissions

The sample prices and menu are fictional. No payment is collected by this starter project.
