from pathlib import Path

path = Path("app.py")
source = path.read_text()

marker = "# ---------- OWNER REPORTS ----------"

if 'elif page == "Sales & Billing":' in source:
    print("Sales & Billing already exists. No changes made.")
    raise SystemExit

if marker not in source:
    print("Could not find the Owner Reports section. No changes made.")
    raise SystemExit

source = source.replace(
    "import hmac\n",
    "import hmac\nfrom datetime import datetime\n",
    1
)

source = source.replace(
    'pages = ["Dashboard", "Products"]',
    'pages = ["Dashboard", "Products", "Sales & Billing"]',
    1
)

billing = r'''
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

                                conn.execute("""
                                    UPDATE products
                                    SET stock = stock - ?
                                    WHERE id = ?
                                """, (
                                    item["quantity"],
                                    item["product_id"]
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
        st.caption("PDF printing will be added in a later step.")

'''

source = source.replace(marker, billing + "\n" + marker, 1)
path.write_text(source)
print("Sales & Billing code added to app.py.")
