
import hashlib
import hmac
from datetime import datetime
import streamlit as st
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from db import initialize_database, get_connection

st.set_page_config(
    page_title="RR Sanitary",
    page_icon="🏪",
    layout="wide"
)

initialize_database()


def create_invoice_pdf(bill):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 50

    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(40, y, "RR SANITARY")
    y -= 28

    pdf.setFont("Helvetica", 10)
    pdf.drawString(40, y, "Customer Invoice")
    y -= 24
    pdf.drawString(40, y, f"Invoice: {bill['invoice_no']}")
    y -= 16
    pdf.drawString(40, y, f"Customer: {bill['customer']}")
    y -= 16
    pdf.drawString(40, y, f"Phone: {bill['phone'] or '-'}")
    y -= 28

    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(40, y, "Product")
    pdf.drawString(270, y, "Qty")
    pdf.drawString(330, y, "Price (NPR)")
    pdf.drawString(440, y, "Total (NPR)")
    y -= 8
    pdf.line(40, y, 555, y)
    y -= 18

    pdf.setFont("Helvetica", 9)
    for item in bill["items"]:
        if y < 100:
            pdf.showPage()
            y = height - 50
            pdf.setFont("Helvetica", 9)

        name = item["name"][:38]
        pdf.drawString(40, y, name)
        pdf.drawRightString(305, y, f"{item['quantity']:g}")
        pdf.drawRightString(410, y, f"{item['unit_price']:,.2f}")
        pdf.drawRightString(555, y, f"{item['line_total']:,.2f}")
        y -= 18

    y -= 10
    pdf.line(330, y, 555, y)
    y -= 20

    pdf.setFont("Helvetica", 10)
    pdf.drawRightString(555, y, f"Subtotal: NPR {bill['subtotal']:,.2f}")
    y -= 18
    pdf.drawRightString(555, y, f"Discount: NPR {bill['discount']:,.2f}")
    y -= 18

    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawRightString(555, y, f"Total: NPR {bill['total']:,.2f}")
    y -= 20

    pdf.setFont("Helvetica", 10)
    pdf.drawRightString(555, y, f"Received: NPR {bill['paid']:,.2f}")
    y -= 18
    pdf.drawRightString(555, y, f"Due: NPR {bill['due']:,.2f}")
    y -= 18
    pdf.drawString(40, y, f"Payment: {bill['payment_method']}")
    y -= 35
    pdf.drawString(40, y, "Thank you for your business!")

    pdf.save()
    buffer.seek(0)
    return buffer.getvalue()
# ---------- LOGIN SYSTEM ----------

def verify_password(password, salt, saved_hash):
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        600000
    ).hex()

    return hmac.compare_digest(password_hash, saved_hash)


if "role" not in st.session_state:
    st.session_state.role = None


if st.session_state.role is None:
    st.title("🏪 RR Sanitary")
    st.subheader("Login to RR Sanitary")

    try:
        auth = st.secrets["auth"]
    except Exception:
        st.error(
            "Login settings not found. Check "
            ".streamlit/secrets.toml"
        )
        st.stop()

    with st.form("login_form"):
        role_choice = st.selectbox(
            "Login as",
            ["Staff", "Owner"]
        )

        password = st.text_input(
            "Password",
            type="password"
        )

        login_clicked = st.form_submit_button("Login")

        if login_clicked:
            role_key = role_choice.lower()

            salt = auth[f"{role_key}_salt"]
            saved_hash = auth[f"{role_key}_hash"]

            if verify_password(password, salt, saved_hash):
                st.session_state.role = role_key
                st.rerun()
            else:
                st.error("Incorrect password. Please try again.")

    st.stop()


# ---------- ACCESS CONTROL ----------

role = st.session_state.role
is_owner = role == "owner"

st.title("🏪 RR Sanitary")
st.caption("Hardware Shop Accounting | Nepal | NPR")

st.sidebar.write(
    f"Logged in as: **{role.title()}**"
)

if st.sidebar.button("Logout"):
    st.session_state.role = None
    st.rerun()


# ---------- DASHBOARD ----------

with get_connection() as conn:
    total_products = conn.execute(
        "SELECT COUNT(*) FROM products"
    ).fetchone()[0]

    if is_owner:
        total_stock_value = conn.execute(
            "SELECT COALESCE(SUM(stock * cost_price), 0) "
            "FROM products"
        ).fetchone()[0]


pages = ["Dashboard", "Products", "Stock Adjustment", "Sales & Billing", "Purchases"]

if is_owner:
    pages.extend(["Sales History", "Expenses", "Owner Reports", "Customer & Supplier Ledger", "Manage & Delete Records"])

page = st.sidebar.selectbox("Navigation", pages)


if page == "Dashboard":
    st.subheader("Welcome to Hardware Khata")

    col1, col2 = st.columns(2)

    col1.metric("Total Products", total_products)

    if is_owner:
        col2.metric(
            "Stock Cost Value",
            f"रु. {total_stock_value:,.2f}"
        )
        st.info(
            "Sales, purchases and profit reports will be "
            "available after those modules are implemented."
        )
    else:
        st.info(
            "You have staff access. Financial totals and "
            "purchase costs are hidden."
        )


# ---------- PRODUCTS ----------

elif page == "Products":
    st.subheader("Product Inventory")

    with st.form("product_form"):
        name = st.text_input("Product Name")
        category = st.text_input("Category")

        unit = st.selectbox(
            "Unit",
            ["pcs", "kg", "bag", "box", "meter", "liter", "set"]
        )

        if is_owner:
            cost = st.number_input(
                "Purchase Price (NPR)",
                min_value=0.0
            )
        else:
            cost = 0.0

        selling = st.number_input(
            "Selling Price (NPR)",
            min_value=0.0
        )

        stock = st.number_input(
            "Opening Stock",
            min_value=0.0
        )

        submitted = st.form_submit_button("Save Product")

        if submitted:
            if not name.strip():
                st.error("Enter a product name.")
            else:
                try:
                    with get_connection() as conn:
                        conn.execute(
                            """
                            INSERT INTO products
                            (name, category, unit, cost_price,
                             selling_price, stock)
                            VALUES (?, ?, ?, ?, ?, ?)
                            """,
                            (
                                name.strip(),
                                category.strip(),
                                unit,
                                cost,
                                selling,
                                stock
                            )
                        )

                    st.success("Product saved!")
                    st.rerun()

                except Exception:
                    st.error(
                        "Product already exists or could not be saved."
                    )

    with get_connection() as conn:
        if is_owner:
            rows = conn.execute(
                "SELECT * FROM products ORDER BY name"
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, name, category, unit,
                       selling_price, stock
                FROM products
                ORDER BY name
                """
            ).fetchall()

    if rows:
        st.dataframe(
            [dict(row) for row in rows],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No products added yet.")

    # Only the owner can update purchase costs.
    if is_owner and rows:
        st.divider()
        st.subheader("Update Purchase Cost")

        product_names = [row["name"] for row in rows]

        with st.form("update_cost_form"):
            selected_product = st.selectbox(
                "Select Product",
                product_names
            )

            new_cost = st.number_input(
                "New Purchase Cost (NPR)",
                min_value=0.0
            )

            update_clicked = st.form_submit_button(
                "Update Cost"
            )

            if update_clicked:
                with get_connection() as conn:
                    conn.execute(
                        """
                        UPDATE products
                        SET cost_price = ?
                        WHERE name = ?
                        """,
                        (new_cost, selected_product)
                    )

                st.success("Purchase cost updated!")
                st.rerun()


    # Edit product details without changing stock silently.
    if rows:
        st.divider()
        st.subheader("Edit Product Details")
        st.caption("Change the product name, category, unit, and prices here. Use Stock Adjustment to correct quantities so changes are recorded.")
        product_choices = {f"{row['name']} (ID {row['id']})": row for row in rows}
        selected_label = st.selectbox("Choose product to edit", list(product_choices.keys()), key="edit_product_choice")
        selected_row = product_choices[selected_label]
        with st.form("edit_product_form"):
            edit_name = st.text_input("Product name", value=selected_row["name"])
            edit_category = st.text_input("Category", value=selected_row["category"] or "")
            units = ["pcs", "kg", "bag", "box", "meter", "liter", "set"]
            selected_unit = selected_row["unit"] if selected_row["unit"] in units else "pcs"
            edit_unit = st.selectbox("Unit", units, index=units.index(selected_unit))
            if is_owner:
                edit_cost = st.number_input("Purchase cost (NPR)", min_value=0.0, value=float(selected_row["cost_price"] or 0), step=1.0, key="edit_cost_value")
            else:
                edit_cost = None
            edit_selling = st.number_input("Selling price (NPR)", min_value=0.0, value=float(selected_row["selling_price"] or 0), step=1.0, key="edit_selling_value")
            save_edit = st.form_submit_button("Save Product Changes")
        if save_edit:
            if not edit_name.strip():
                st.error("Product name cannot be empty.")
            else:
                try:
                    with get_connection() as conn:
                        if is_owner:
                            conn.execute("UPDATE products SET name=?, category=?, unit=?, cost_price=?, selling_price=? WHERE id=?", (edit_name.strip(), edit_category.strip(), edit_unit, edit_cost, edit_selling, selected_row["id"]))
                        else:
                            conn.execute("UPDATE products SET name=?, category=?, unit=?, selling_price=? WHERE id=?", (edit_name.strip(), edit_category.strip(), edit_unit, edit_selling, selected_row["id"]))
                    st.success("Product details updated.")
                    st.rerun()
                except Exception:
                    st.error("Could not update product. Check whether another product already uses that name.")


# ---------- STOCK ADJUSTMENT ----------
elif page == "Stock Adjustment":
    st.subheader("Stock Adjustment")
    st.caption("Use this when you count the shelf and the actual quantity differs from the system. Every adjustment is logged with a reason.")
    with get_connection() as conn:
        stock_products = conn.execute("SELECT id, name, unit, stock FROM products ORDER BY name").fetchall()
    if not stock_products:
        st.info("Add products first.")
    else:
        stock_map = {f"{x['name']} — current stock: {x['stock']:g} {x['unit']}": x for x in stock_products}
        with st.form("stock_adjust_form"):
            chosen_stock_label = st.selectbox("Product", list(stock_map.keys()))
            chosen_stock = stock_map[chosen_stock_label]
            actual_stock = st.number_input("Actual counted quantity", min_value=0.0, value=float(chosen_stock["stock"]), step=1.0)
            adjustment_reason = st.selectbox("Reason", ["Physical stock count", "Damaged goods", "Lost/missing stock", "Opening correction", "Other"])
            adjustment_note = st.text_input("Notes (optional)")
            adjust_submit = st.form_submit_button("Save Stock Correction")
        if adjust_submit:
            delta = float(actual_stock) - float(chosen_stock["stock"])
            if abs(delta) < 0.000001:
                st.info("The actual quantity matches the current stock. No change was needed.")
            else:
                try:
                    with get_connection() as conn:
                        current = conn.execute("SELECT stock FROM products WHERE id=?", (chosen_stock["id"],)).fetchone()
                        if current is None:
                            raise ValueError("Product no longer exists. Refresh and try again.")
                        before = float(current["stock"])
                        delta = float(actual_stock) - before
                        conn.execute("UPDATE products SET stock=? WHERE id=?", (float(actual_stock), chosen_stock["id"]))
                        conn.execute("INSERT INTO stock_movements(product_id, product_name, movement_type, quantity_change, stock_before, stock_after, reason, notes, created_by) VALUES(?,?,?,?,?,?,?,?,?)", (chosen_stock["id"], chosen_stock["name"], "ADJUSTMENT", delta, before, float(actual_stock), adjustment_reason, adjustment_note.strip(), role))
                    st.success(f"Stock updated: {before:g} → {float(actual_stock):g} {chosen_stock['unit']}.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Stock correction was not saved: {exc}")
    st.divider()
    st.subheader("Recent Stock Changes")
    with get_connection() as conn:
        movements = conn.execute("SELECT created_at, product_name, movement_type, quantity_change, stock_before, stock_after, reason, notes, created_by FROM stock_movements ORDER BY id DESC LIMIT 100").fetchall()
    if movements:
        st.dataframe([dict(x) for x in movements], use_container_width=True, hide_index=True)
    else:
        st.info("No stock adjustments have been recorded yet.")



# ---------- SALES & BILLING ----------
elif page == "Sales & Billing":
    st.subheader("Sales & Billing")

    with get_connection() as conn:
        products = conn.execute("""
            SELECT id, name, unit, selling_price, stock
            FROM products
            ORDER BY name
        """).fetchall()

    if not products:
        st.warning("Add products in Products before creating a bill.")
    else:
        if "sales_cart" not in st.session_state:
            st.session_state.sales_cart = []

        product_map = {p["name"]: p for p in products}

        st.markdown("### 1. Add products to the bill")

        with st.form("add_to_cart_form"):
            selected_name = st.selectbox(
                "Select product",
                list(product_map.keys())
            )
            selected_product = product_map[selected_name]
            st.caption(
                f"Selling price: NPR {selected_product['selling_price']:,.2f} "
                f"per {selected_product['unit']} | "
                f"Available stock: {selected_product['stock']:g}"
            )
            quantity = st.number_input(
                "Quantity",
                min_value=0.01,
                value=1.0,
                step=1.0
            )
            add_clicked = st.form_submit_button("Add to Bill")

        if add_clicked:
            product = product_map[selected_name]
            already_in_cart = sum(
                item["quantity"]
                for item in st.session_state.sales_cart
                if item["product_id"] == product["id"]
            )
            if quantity + already_in_cart > product["stock"]:
                st.error("Quantity exceeds available stock.")
            else:
                existing = next(
                    (
                        item for item in st.session_state.sales_cart
                        if item["product_id"] == product["id"]
                    ),
                    None
                )
                if existing:
                    existing["quantity"] += quantity
                    existing["line_total"] = (
                        existing["quantity"] * existing["unit_price"]
                    )
                else:
                    st.session_state.sales_cart.append({
                        "product_id": product["id"],
                        "name": product["name"],
                        "unit": product["unit"],
                        "quantity": quantity,
                        "unit_price": product["selling_price"],
                        "line_total": quantity * product["selling_price"]
                    })
                st.rerun()

        cart = st.session_state.sales_cart

        if cart:
            st.markdown("### 2. Current bill")
            st.dataframe(
                [
                    {
                        "Product": item["name"],
                        "Quantity": item["quantity"],
                        "Unit": item["unit"],
                        "Selling Price (NPR)": item["unit_price"],
                        "Line Total (NPR)": item["line_total"]
                    }
                    for item in cart
                ],
                use_container_width=True,
                hide_index=True
            )

            subtotal = sum(item["line_total"] for item in cart)
            st.write(f"**Subtotal: NPR {subtotal:,.2f}**")

            remove_options = [
                f"{i + 1}. {item['name']}"
                for i, item in enumerate(cart)
            ]
            remove_choice = st.selectbox(
                "Remove a product (optional)",
                ["Do not remove"] + remove_options,
                key="remove_cart_choice"
            )
            col_remove, col_clear = st.columns(2)
            if col_remove.button("Remove Selected"):
                if remove_choice != "Do not remove":
                    index = remove_options.index(remove_choice)
                    st.session_state.sales_cart.pop(index)
                    st.rerun()
            if col_clear.button("Clear Entire Bill"):
                st.session_state.sales_cart = []
                st.rerun()

            st.markdown("### 3. Customer and payment")

            customer_name = st.text_input(
                "Customer Name",
                value="Walk-in Customer",
                key="billing_customer_name"
            )
            customer_phone = st.text_input(
                "Customer Phone (optional)",
                key="billing_customer_phone"
            )
            discount = st.number_input(
                "Discount (NPR)",
                min_value=0.0,
                max_value=float(subtotal),
                value=0.0,
                key="billing_discount"
            )
            total = subtotal - discount
            st.write(f"**Bill Total: NPR {total:,.2f}**")

            amount_paid = st.number_input(
                "Amount Received (NPR)",
                min_value=0.0,
                max_value=float(total),
                value=float(total),
                key="billing_amount_paid"
            )
            payment_method = st.selectbox(
                "Payment Method",
                ["Cash", "Bank Transfer", "QR Payment", "Credit"]
            )

            st.write(f"**Amount Due: NPR {total - amount_paid:,.2f}**")

            if st.button("Save Sale and Update Stock", type="primary"):
                if not customer_name.strip():
                    st.error("Enter a customer name.")
                else:
                    try:
                        with get_connection() as conn:
                            # Recheck stock immediately before saving.
                            for item in cart:
                                row = conn.execute(
                                    "SELECT stock FROM products WHERE id = ?",
                                    (item["product_id"],)
                                ).fetchone()
                                if (
                                    row is None
                                    or row["stock"] < item["quantity"]
                                ):
                                    raise ValueError(
                                        "Stock changed. Refresh the bill "
                                        "and check available quantities."
                                    )

                            invoice_no = (
                                "HK-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f")
                            )

                            cursor = conn.execute("""
                                INSERT INTO sales (
                                    invoice_no, customer_name, customer_phone,
                                    subtotal, discount, total, amount_paid,
                                    payment_method
                                )
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                invoice_no,
                                customer_name.strip(),
                                customer_phone.strip(),
                                subtotal,
                                discount,
                                total,
                                amount_paid,
                                payment_method
                            ))
                            sale_id = cursor.lastrowid

                            for item in cart:
                                conn.execute("""
                                    INSERT INTO sale_items (
                                        sale_id, product_id, product_name,
                                        quantity, unit_price, line_total
                                    )
                                    VALUES (?, ?, ?, ?, ?, ?)
                                """, (
                                    sale_id,
                                    item["product_id"],
                                    item["name"],
                                    item["quantity"],
                                    item["unit_price"],
                                    item["line_total"]
                                ))

                                stock_before = conn.execute(
                                    "SELECT stock FROM products WHERE id = ?",
                                    (item["product_id"],)
                                ).fetchone()["stock"] + item["quantity"]
                                stock_after = stock_before - item["quantity"]
                                conn.execute("""
                                    UPDATE products
                                    SET stock = ?
                                    WHERE id = ?
                                """, (
                                    stock_after,
                                    item["product_id"]
                                ))
                                conn.execute("""
                                    INSERT INTO stock_movements (
                                        product_id, product_name, movement_type,
                                        quantity_change, stock_before, stock_after,
                                        reason, notes, created_by
                                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """, (
                                    item["product_id"], item["name"], "SALE",
                                    -item["quantity"], stock_before, stock_after,
                                    "Sale completed", f"Invoice {invoice_no}", role
                                ))

                        st.session_state.last_invoice = {
                            "invoice_no": invoice_no,
                            "customer": customer_name.strip(),
                            "phone": customer_phone.strip(),
                            "items": [dict(item) for item in cart],
                            "subtotal": subtotal,
                            "discount": discount,
                            "total": total,
                            "paid": amount_paid,
                            "due": total - amount_paid,
                            "payment_method": payment_method
                        }
                        st.session_state.sales_cart = []
                        st.success(f"Sale saved! Invoice: {invoice_no}")
                        st.rerun()

                    except Exception as exc:
                        st.error(f"Sale was not saved: {exc}")

        else:
            st.info("Your bill is empty. Add a product above.")

    if "last_invoice" in st.session_state:
        bill = st.session_state.last_invoice
        st.divider()
        st.markdown("### Last saved invoice")
        st.write(f"**Invoice:** {bill['invoice_no']}")
        st.write(f"**Customer:** {bill['customer']}")
        st.write(f"**Phone:** {bill['phone'] or '-'}")
        st.dataframe(
            [
                {
                    "Product": item["name"],
                    "Quantity": item["quantity"],
                    "Unit": item["unit"],
                    "Price (NPR)": item["unit_price"],
                    "Total (NPR)": item["line_total"]
                }
                for item in bill["items"]
            ],
            use_container_width=True,
            hide_index=True
        )
        st.write(f"Subtotal: NPR {bill['subtotal']:,.2f}")
        st.write(f"Discount: NPR {bill['discount']:,.2f}")
        st.write(f"**Total: NPR {bill['total']:,.2f}**")
        st.write(f"Received: NPR {bill['paid']:,.2f}")
        st.write(f"Due: NPR {bill['due']:,.2f}")
        st.write(f"Payment method: {bill['payment_method']}")
        pdf_bytes = create_invoice_pdf(bill)

        st.download_button(
            label="Download Invoice PDF",
            data=pdf_bytes,
            file_name=f"{bill['invoice_no']}.pdf",
            mime="application/pdf"
        )


# ---------- PURCHASES ----------
elif page == "Purchases":
    if not is_owner:
        st.error("Only the owner can access purchases and purchase costs.")
        st.stop()
    st.subheader("Purchase Entry")
    st.caption("Record incoming goods here. Saving a purchase increases stock and records supplier and purchase-cost details.")
    with get_connection() as conn:
        purchase_products = conn.execute("SELECT id, name, unit, stock FROM products ORDER BY name").fetchall()
    if not purchase_products:
        st.info("Add products before recording purchases.")
    else:
        purchase_map = {x["name"]: x for x in purchase_products}
        with st.form("purchase_entry_form"):
            supplier_name = st.text_input("Supplier name")
            supplier_phone = st.text_input("Supplier phone (optional)")
            supplier_invoice = st.text_input("Supplier invoice/reference (optional)")
            purchase_product_name = st.selectbox("Product received", list(purchase_map.keys()))
            purchase_product = purchase_map[purchase_product_name]
            purchase_qty = st.number_input("Quantity received", min_value=0.01, value=1.0, step=1.0)
            purchase_cost = st.number_input("Cost per unit (NPR)", min_value=0.0, step=1.0)
            purchase_discount = st.number_input("Purchase discount (NPR)", min_value=0.0, step=1.0)
            purchase_paid = st.number_input("Amount paid to supplier (NPR)", min_value=0.0, step=1.0)
            purchase_method = st.selectbox("Payment method", ["Cash", "Bank Transfer", "QR Payment", "Credit"])
            purchase_notes = st.text_input("Notes (optional)")
            purchase_submit = st.form_submit_button("Save Purchase and Add Stock", type="primary")
        purchase_subtotal = purchase_qty * purchase_cost
        purchase_total = max(0.0, purchase_subtotal - purchase_discount)
        st.write(f"**Purchase total: NPR {purchase_total:,.2f}**")
        if purchase_submit:
            if not is_owner:
                st.error("Only the owner can record purchases because they include purchase costs.")
            elif not supplier_name.strip():
                st.error("Enter the supplier name.")
            elif purchase_discount > purchase_subtotal:
                st.error("Discount cannot be greater than the purchase subtotal.")
            elif purchase_paid > purchase_total:
                st.error("Amount paid cannot exceed the purchase total. Enter the actual amount paid.")
            else:
                try:
                    with get_connection() as conn:
                        current = conn.execute("SELECT stock, cost_price FROM products WHERE id=?", (purchase_product["id"],)).fetchone()
                        if current is None:
                            raise ValueError("Product not found. Refresh and try again.")
                        cursor = conn.execute("INSERT INTO purchases(supplier_name, supplier_phone, supplier_invoice, subtotal, discount, total, amount_paid, payment_method, notes, created_by) VALUES(?,?,?,?,?,?,?,?,?,?)", (supplier_name.strip(), supplier_phone.strip(), supplier_invoice.strip(), purchase_subtotal, purchase_discount, purchase_total, purchase_paid, purchase_method, purchase_notes.strip(), role))
                        purchase_id = cursor.lastrowid
                        conn.execute("INSERT INTO purchase_items(purchase_id, product_id, product_name, quantity, unit_cost, line_total) VALUES(?,?,?,?,?,?)", (purchase_id, purchase_product["id"], purchase_product["name"], purchase_qty, purchase_cost, purchase_subtotal))
                        new_stock = float(current["stock"]) + float(purchase_qty)
                        conn.execute("UPDATE products SET stock=?, cost_price=? WHERE id=?", (new_stock, purchase_cost, purchase_product["id"]))
                        conn.execute("INSERT INTO stock_movements(product_id, product_name, movement_type, quantity_change, stock_before, stock_after, reason, notes, created_by) VALUES(?,?,?,?,?,?,?,?,?)", (purchase_product["id"], purchase_product["name"], "PURCHASE", purchase_qty, current["stock"], new_stock, "Purchase received", f"Supplier: {supplier_name.strip()}; Ref: {supplier_invoice.strip()}", role))
                    st.success(f"Purchase saved. Stock for {purchase_product['name']} is now {new_stock:g} {purchase_product['unit']}.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Purchase was not saved: {exc}")
    if is_owner:
        st.divider()
        st.subheader("Recent Purchases")
        with get_connection() as conn:
            recent_purchases = conn.execute("SELECT id, purchase_date, supplier_name, supplier_invoice, total, amount_paid, (total-amount_paid) AS due, payment_method FROM purchases ORDER BY id DESC LIMIT 100").fetchall()
        if recent_purchases:
            st.dataframe([dict(x) for x in recent_purchases], use_container_width=True, hide_index=True)
        else:
            st.info("No purchases recorded yet.")




# ---------- MANAGE & DELETE RECORDS (OWNER ONLY) ----------
elif page == "Manage & Delete Records":
    st.subheader("Manage & Delete Records")

    if not is_owner:
        st.error("Owner access required.")
        st.stop()

    st.warning(
        "Deletion is permanent. Review the selected record carefully "
        "before confirming. Financial invoices and purchases are not "
        "deleted from this page."
    )

    product_tab, customer_tab, supplier_tab, expense_tab = st.tabs(
        ["Products", "Customers", "Suppliers", "Expenses"]
    )

    with product_tab:
        st.markdown("#### Delete a product")
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT id, name, stock FROM products ORDER BY name"
            ).fetchall()

        if rows:
            options = {
                f"{r['name']} | Stock: {r['stock']} | ID: {r['id']}": dict(r)
                for r in rows
            }
            label = st.selectbox(
                "Select product",
                list(options),
                key="delete_product_choice"
            )
            item = options[label]
            st.write(f"Selected: **{item['name']}**")

            confirm = st.checkbox(
                "I confirm I want to delete this product.",
                key="confirm_delete_product"
            )
            if st.button(
                "Delete Product",
                type="secondary",
                key="delete_product_button"
            ):
                if not confirm:
                    st.error("Confirm the deletion first.")
                else:
                    with get_connection() as conn:
                        used_in_sales = conn.execute(
                            "SELECT COUNT(*) FROM sale_items WHERE product_id=?",
                            (item["id"],)
                        ).fetchone()[0]
                        used_in_purchases = conn.execute(
                            "SELECT COUNT(*) FROM purchase_items WHERE product_id=?",
                            (item["id"],)
                        ).fetchone()[0]

                        if used_in_sales or used_in_purchases:
                            st.error(
                                "This product appears in historical invoices "
                                "or purchases. It cannot be deleted here; "
                                "keep it to preserve accounting history."
                            )
                        else:
                            conn.execute(
                                "DELETE FROM products WHERE id=?",
                                (item["id"],)
                            )
                            st.success("Product deleted.")
                            st.rerun()
        else:
            st.info("No products available.")

    with customer_tab:
        st.markdown("#### Delete a customer record")
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT id, name, phone FROM customers ORDER BY name"
            ).fetchall()

        if rows:
            options = {
                f"{r['name']} | {r['phone'] or 'No phone'} | ID: {r['id']}": dict(r)
                for r in rows
            }
            label = st.selectbox(
                "Select customer",
                list(options),
                key="delete_customer_choice"
            )
            item = options[label]
            st.caption(
                "This removes the customer directory entry only. "
                "Historical sales retain their recorded customer names."
            )
            confirm = st.checkbox(
                "I confirm I want to delete this customer record.",
                key="confirm_delete_customer"
            )
            if st.button(
                "Delete Customer",
                key="delete_customer_button"
            ):
                if not confirm:
                    st.error("Confirm the deletion first.")
                else:
                    with get_connection() as conn:
                        conn.execute(
                            "DELETE FROM customers WHERE id=?",
                            (item["id"],)
                        )
                    st.success("Customer record deleted.")
                    st.rerun()
        else:
            st.info("No customer records available.")

    with supplier_tab:
        st.markdown("#### Delete a supplier record")
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT id, name, phone FROM suppliers ORDER BY name"
            ).fetchall()

        if rows:
            options = {
                f"{r['name']} | {r['phone'] or 'No phone'} | ID: {r['id']}": dict(r)
                for r in rows
            }
            label = st.selectbox(
                "Select supplier",
                list(options),
                key="delete_supplier_choice"
            )
            item = options[label]
            st.caption(
                "This removes the supplier directory entry only. "
                "Historical purchases retain their recorded supplier names."
            )
            confirm = st.checkbox(
                "I confirm I want to delete this supplier record.",
                key="confirm_delete_supplier"
            )
            if st.button(
                "Delete Supplier",
                key="delete_supplier_button"
            ):
                if not confirm:
                    st.error("Confirm the deletion first.")
                else:
                    with get_connection() as conn:
                        conn.execute(
                            "DELETE FROM suppliers WHERE id=?",
                            (item["id"],)
                        )
                    st.success("Supplier record deleted.")
                    st.rerun()
        else:
            st.info("No supplier records available.")

    with expense_tab:
        st.markdown("#### Delete an expense")
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT id, expense_date, category, description, amount "
                "FROM expenses ORDER BY id DESC"
            ).fetchall()

        if rows:
            options = {
                f"ID {r['id']} | {r['expense_date']} | "
                f"{r['description']} | NPR {float(r['amount']):,.2f}": dict(r)
                for r in rows
            }
            label = st.selectbox(
                "Select expense",
                list(options),
                key="delete_expense_choice"
            )
            item = options[label]
            confirm = st.checkbox(
                "I confirm I want to permanently delete this expense.",
                key="confirm_delete_expense"
            )
            if st.button(
                "Delete Expense",
                key="delete_expense_button"
            ):
                if not confirm:
                    st.error("Confirm the deletion first.")
                else:
                    with get_connection() as conn:
                        conn.execute(
                            "DELETE FROM expenses WHERE id=?",
                            (item["id"],)
                        )
                    st.success("Expense deleted.")
                    st.rerun()
        else:
            st.info("No expenses available.")


# ---------- CUSTOMER & SUPPLIER LEDGER (OWNER ONLY) ----------
elif page == "Customer & Supplier Ledger":
    st.subheader("Customer & Supplier Ledger")

    if not is_owner:
        st.error("Owner access required.")
        st.stop()

    st.caption(
        "Balances include opening balances, invoices, and payments "
        "recorded against those invoices. Separate later-payment entries "
        "are not supported by the current database."
    )

    with get_connection() as conn:
        customer_master = conn.execute(
            "SELECT name, phone, opening_balance FROM customers ORDER BY name"
        ).fetchall()

        customer_sales = conn.execute(
            "SELECT customer_name AS name, "
            "MAX(customer_phone) AS phone, "
            "COALESCE(SUM(total), 0) AS total_sales, "
            "COALESCE(SUM(amount_paid), 0) AS amount_paid "
            "FROM sales GROUP BY customer_name ORDER BY customer_name"
        ).fetchall()

        supplier_master = conn.execute(
            "SELECT name, phone, opening_balance FROM suppliers ORDER BY name"
        ).fetchall()

        supplier_purchases = conn.execute(
            "SELECT supplier_name AS name, "
            "MAX(supplier_phone) AS phone, "
            "COALESCE(SUM(total), 0) AS total_purchases, "
            "COALESCE(SUM(amount_paid), 0) AS amount_paid "
            "FROM purchases GROUP BY supplier_name ORDER BY supplier_name"
        ).fetchall()

    customer_data = {}

    for row in customer_master:
        name = (row["name"] or "").strip()
        key = name.casefold()
        if not key:
            continue

        entry = customer_data.setdefault(key, {
            "Customer": name,
            "Phone": row["phone"] or "",
            "Opening Balance (NPR)": 0.0,
            "Total Sales (NPR)": 0.0,
            "Payments Received (NPR)": 0.0,
        })
        entry["Opening Balance (NPR)"] += float(row["opening_balance"] or 0)

    for row in customer_sales:
        name = (row["name"] or "").strip()
        key = name.casefold()
        if not key:
            continue

        entry = customer_data.setdefault(key, {
            "Customer": name,
            "Phone": row["phone"] or "",
            "Opening Balance (NPR)": 0.0,
            "Total Sales (NPR)": 0.0,
            "Payments Received (NPR)": 0.0,
        })
        if not entry["Phone"]:
            entry["Phone"] = row["phone"] or ""
        entry["Total Sales (NPR)"] += float(row["total_sales"] or 0)
        entry["Payments Received (NPR)"] += float(row["amount_paid"] or 0)

    for entry in customer_data.values():
        entry["Outstanding Balance (NPR)"] = (
            entry["Opening Balance (NPR)"]
            + entry["Total Sales (NPR)"]
            - entry["Payments Received (NPR)"]
        )

    supplier_data = {}

    for row in supplier_master:
        name = (row["name"] or "").strip()
        key = name.casefold()
        if not key:
            continue

        entry = supplier_data.setdefault(key, {
            "Supplier": name,
            "Phone": row["phone"] or "",
            "Opening Balance (NPR)": 0.0,
            "Total Purchases (NPR)": 0.0,
            "Payments Made (NPR)": 0.0,
        })
        entry["Opening Balance (NPR)"] += float(row["opening_balance"] or 0)

    for row in supplier_purchases:
        name = (row["name"] or "").strip()
        key = name.casefold()
        if not key:
            continue

        entry = supplier_data.setdefault(key, {
            "Supplier": name,
            "Phone": row["phone"] or "",
            "Opening Balance (NPR)": 0.0,
            "Total Purchases (NPR)": 0.0,
            "Payments Made (NPR)": 0.0,
        })
        if not entry["Phone"]:
            entry["Phone"] = row["phone"] or ""
        entry["Total Purchases (NPR)"] += float(row["total_purchases"] or 0)
        entry["Payments Made (NPR)"] += float(row["amount_paid"] or 0)

    for entry in supplier_data.values():
        entry["Outstanding Balance (NPR)"] = (
            entry["Opening Balance (NPR)"]
            + entry["Total Purchases (NPR)"]
            - entry["Payments Made (NPR)"]
        )

    customer_tab, supplier_tab = st.tabs(
        ["Customer Ledger", "Supplier Ledger"]
    )

    with customer_tab:
        st.markdown("#### Customer balances")

        customer_rows = sorted(
            customer_data.values(),
            key=lambda item: item["Customer"].casefold()
        )

        if customer_rows:
            st.dataframe(customer_rows, use_container_width=True, hide_index=True)
            st.metric(
                "Total customer outstanding",
                "NPR {:,.2f}".format(
                    sum(x["Outstanding Balance (NPR)"] for x in customer_rows)
                )
            )

            names = [x["Customer"] for x in customer_rows]
            selected_customer = st.selectbox(
                "View customer invoices",
                names,
                key="ledger_customer_select"
            )

            with get_connection() as conn:
                invoices = conn.execute(
                    "SELECT invoice_no, sale_date, total, amount_paid, "
                    "(total - amount_paid) AS due, payment_method "
                    "FROM sales WHERE customer_name = ? ORDER BY id DESC",
                    (selected_customer,)
                ).fetchall()

            st.markdown("#### Invoice history")
            if invoices:
                st.dataframe(
                    [dict(x) for x in invoices],
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("No invoices found for this customer.")
        else:
            st.info("No customer records or sales found yet.")

    with supplier_tab:
        st.markdown("#### Supplier balances")

        supplier_rows = sorted(
            supplier_data.values(),
            key=lambda item: item["Supplier"].casefold()
        )

        if supplier_rows:
            st.dataframe(supplier_rows, use_container_width=True, hide_index=True)
            st.metric(
                "Total supplier outstanding",
                "NPR {:,.2f}".format(
                    sum(x["Outstanding Balance (NPR)"] for x in supplier_rows)
                )
            )

            names = [x["Supplier"] for x in supplier_rows]
            selected_supplier = st.selectbox(
                "View supplier purchases",
                names,
                key="ledger_supplier_select"
            )

            with get_connection() as conn:
                purchases = conn.execute(
                    "SELECT purchase_date, supplier_invoice, total, amount_paid, "
                    "(total - amount_paid) AS due, payment_method "
                    "FROM purchases WHERE supplier_name = ? ORDER BY id DESC",
                    (selected_supplier,)
                ).fetchall()

            st.markdown("#### Purchase history")
            if purchases:
                st.dataframe(
                    [dict(x) for x in purchases],
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("No purchases found for this supplier.")
        else:
            st.info("No supplier records or purchases found yet.")


# ---------- SALES HISTORY (OWNER ONLY) ----------
elif page == "Sales History":
    st.subheader("Sales History")
    if not is_owner:
        st.error("Owner access required.")
        st.stop()
    with get_connection() as conn:
        sales_rows = conn.execute("SELECT id, invoice_no, sale_date, customer_name, customer_phone, subtotal, discount, total, amount_paid, (total-amount_paid) AS due, payment_method FROM sales ORDER BY id DESC LIMIT 500").fetchall()
    if sales_rows:
        st.dataframe([dict(x) for x in sales_rows], use_container_width=True, hide_index=True)
        invoice_labels = {f"{x['invoice_no']} — {x['customer_name']} — NPR {x['total']:,.2f}": x for x in sales_rows}
        chosen_invoice_label = st.selectbox("View invoice items", list(invoice_labels.keys()))
        chosen_invoice = invoice_labels[chosen_invoice_label]
        with get_connection() as conn:
            item_rows = conn.execute("SELECT product_name, quantity, unit_price, line_total FROM sale_items WHERE sale_id=?", (chosen_invoice["id"],)).fetchall()
        st.dataframe([dict(x) for x in item_rows], use_container_width=True, hide_index=True)
        st.caption("Invoices are listed for review. For corrections, use a documented reversal/refund workflow rather than changing historical sales silently.")
    else:
        st.info("No sales have been saved yet.")


# ---------- EXPENSES (OWNER ONLY) ----------
elif page == "Expenses":
    st.subheader("Shop Expenses")
    if not is_owner:
        st.error("Owner access required.")
        st.stop()
    with st.form("expense_form"):
        expense_date = st.date_input("Expense date")
        expense_category = st.selectbox("Category", ["Rent", "Salary", "Transport", "Electricity", "Internet/Phone", "Repair/Maintenance", "Office supplies", "Other"])
        expense_description = st.text_input("Description")
        expense_amount = st.number_input("Amount (NPR)", min_value=0.01, step=100.0)
        expense_method = st.selectbox("Paid by", ["Cash", "Bank Transfer", "QR Payment", "Other"])
        expense_submit = st.form_submit_button("Save Expense")
    if expense_submit:
        if not expense_description.strip():
            st.error("Enter a short description.")
        else:
            with get_connection() as conn:
                conn.execute("INSERT INTO expenses(expense_date, category, description, amount, payment_method, created_by) VALUES(?,?,?,?,?,?)", (expense_date.isoformat(), expense_category, expense_description.strip(), expense_amount, expense_method, role))
            st.success("Expense saved.")
            st.rerun()
    st.divider()
    st.subheader("Recent Expenses")
    with get_connection() as conn:
        expense_rows = conn.execute("SELECT expense_date, category, description, amount, payment_method FROM expenses ORDER BY id DESC LIMIT 200").fetchall()
    if expense_rows:
        st.dataframe([dict(x) for x in expense_rows], use_container_width=True, hide_index=True)
        st.metric("Total shown expenses", f"NPR {sum(float(x['amount']) for x in expense_rows):,.2f}")
    else:
        st.info("No expenses recorded yet.")


# ---------- OWNER REPORTS ----------
elif page == "Owner Reports":
    st.subheader("Owner Reports")

    if not is_owner:
        st.error("Owner access required.")
        st.stop()
    from datetime import date
    report_day = st.date_input("Report date", value=date.today(), key="owner_report_day")
    day_start = report_day.isoformat() + " 00:00:00"
    day_end = report_day.isoformat() + " 23:59:59"
    with get_connection() as conn:
        day_sales = conn.execute("SELECT COUNT(*) AS count, COALESCE(SUM(total),0) AS total, COALESCE(SUM(amount_paid),0) AS paid FROM sales WHERE sale_date BETWEEN ? AND ?", (day_start, day_end)).fetchone()
        day_purchases = conn.execute("SELECT COUNT(*) AS count, COALESCE(SUM(total),0) AS total, COALESCE(SUM(amount_paid),0) AS paid FROM purchases WHERE purchase_date BETWEEN ? AND ?", (day_start, day_end)).fetchone()
        day_expenses = conn.execute("SELECT COALESCE(SUM(amount),0) FROM expenses WHERE expense_date=?", (report_day.isoformat(),)).fetchone()[0]
        stock_value = conn.execute("SELECT COALESCE(SUM(stock*cost_price),0) FROM products").fetchone()[0]
        low_stock = conn.execute("SELECT name, unit, stock FROM products WHERE stock <= 5 ORDER BY stock, name").fetchall()
    c1, c2, c3 = st.columns(3)
    c1.metric("Sales total", f"NPR {day_sales['total']:,.2f}", help=f"{day_sales['count']} bills")
    c2.metric("Purchases total", f"NPR {day_purchases['total']:,.2f}", help=f"{day_purchases['count']} purchase entries")
    c3.metric("Expenses", f"NPR {day_expenses:,.2f}")
    c4, c5, c6 = st.columns(3)
    c4.metric("Sales received", f"NPR {day_sales['paid']:,.2f}")
    c5.metric("Supplier payments", f"NPR {day_purchases['paid']:,.2f}")
    c6.metric("Stock cost value", f"NPR {stock_value:,.2f}")
    st.caption("These are recorded cash-flow and stock figures, not a complete accounting profit statement. Profit needs historical cost/returns and other accounting adjustments.")
    st.divider()
    st.subheader("Low Stock Alert (5 units or less)")
    if low_stock:
        st.dataframe([dict(x) for x in low_stock], use_container_width=True, hide_index=True)
    else:
        st.success("No products currently have 5 units or less.")