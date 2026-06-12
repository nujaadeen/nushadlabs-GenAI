"""
generate_grocery_pdf.py -- Creates FreshMart Grocery knowledge base PDFs.
Run once: python generate_grocery_pdf.py
"""

from pathlib import Path

from fpdf import FPDF, XPos, YPos

RESOURCES = Path(__file__).parent.parent / "resources"


class PDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(60, 140, 60)
        self.cell(0, 8, "FreshMart Grocery Co.  |  Customer & Operations Guide  |  2025",
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
        self.ln(2)
        self.set_draw_color(180, 220, 180)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(3)
        self.set_text_color(0, 0, 0)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 6, f"Page {self.page_no()}  |  hello@freshmart.co  |  freshmart.co", align="C")

    def section_title(self, title: str):
        self.ln(4)
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(40, 120, 40)
        self.cell(0, 8, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(40, 120, 40)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(3)
        self.set_text_color(0, 0, 0)

    def sub_title(self, title: str):
        self.ln(2)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(50, 50, 50)
        self.cell(0, 7, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_text_color(0, 0, 0)

    def body(self, text: str):
        self.set_font("Helvetica", size=10)
        self.multi_cell(0, 5.5, text)
        self.ln(1)

    def bullet(self, items: list):
        self.set_font("Helvetica", size=10)
        indent = 10
        page_w = self.w - self.l_margin - self.r_margin
        for item in items:
            self.cell(indent, 5.5, "* ")
            self.multi_cell(page_w - indent, 5.5, item)
        self.ln(1)

    def price_row(self, name, price, unit="", note=""):
        cols = [80, 35, 40, 35]
        self.set_font("Helvetica", size=9)
        self.cell(cols[0], 6.5, name, border=1)
        self.cell(cols[1], 6.5, price, border=1, align="C")
        self.cell(cols[2], 6.5, unit, border=1, align="C")
        self.cell(cols[3], 6.5, note, border=1,
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def price_header(self, cols_labels=("Item", "Price", "Unit", "Loyalty Price")):
        cols = [80, 35, 40, 35]
        self.set_font("Helvetica", "B", 9)
        self.set_fill_color(40, 120, 40)
        self.set_text_color(255, 255, 255)
        for i, (label, w) in enumerate(zip(cols_labels, cols)):
            last = i == len(cols) - 1
            self.cell(w, 6.5, label, border=1, fill=True,
                      new_x=XPos.LMARGIN if last else XPos.RIGHT,
                      new_y=YPos.NEXT if last else YPos.TOP)
        self.set_text_color(0, 0, 0)


def build_overview_pdf(path: str) -> None:
    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_page()

    # Cover
    pdf.ln(6)
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(40, 120, 40)
    pdf.cell(0, 12, "FreshMart Grocery Co.", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(60, 60, 60)
    pdf.cell(0, 8, "Your Neighbourhood Grocery  |  Customer Guide 2025",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    pdf.body(
        "FreshMart Grocery Co. is a regional grocery chain founded in 2005 and headquartered in "
        "Melbourne, Australia. We operate 12 stores across the Greater Melbourne metropolitan area "
        "and offer home delivery, click-and-collect, and a loyalty rewards programme. Our mission "
        "is to make fresh, high-quality food accessible and affordable for every household."
    )

    # Company Overview
    pdf.section_title("Company Overview")
    pdf.body(
        "Founded in 2005 by siblings Maria and Roberto Ferretti, FreshMart started as a single "
        "store in Fitzroy and has grown steadily by focusing on fresh produce, competitive pricing, "
        "and genuine community relationships. By 2025 we operate 12 stores and employ over 850 "
        "team members across Melbourne. We source more than 60% of our fresh produce directly from "
        "Victorian farms, reducing food miles and supporting local agriculture."
    )
    pdf.bullet([
        "12 stores across Melbourne: Fitzroy, Carlton, South Yarra, Richmond, Hawthorn, Box Hill, "
        "Doncaster, St Kilda, Footscray, Northcote, Brunswick, and Williamstown.",
        "850+ employees, 60% part-time and casual to accommodate student and community workers.",
        "Annual revenue: approximately $180 million (FY 2024).",
        "Online orders: 18% of total revenue and growing at 25% year-on-year.",
        "FreshMart Loyalty Card members: 220,000 active cardholders.",
    ])

    # Store Departments
    pdf.section_title("Store Departments & Product Range")

    pdf.sub_title("Fresh Produce")
    pdf.body(
        "Our produce section is the heart of every FreshMart store. We stock over 300 fruit and "
        "vegetable lines, with a dedicated organic range and a seasonal specials shelf refreshed "
        "weekly. All produce is inspected daily and marked down at 6 pm if approaching best-before "
        "to minimise waste."
    )
    pdf.bullet([
        "Conventional and certified organic fruit and vegetables.",
        "Seasonal specials sourced directly from Victorian farms.",
        "Pre-cut salad bags, stir-fry mixes, and snack packs for convenience.",
        "Herbs (fresh and potted), edible flowers, and specialty Asian vegetables.",
        "Average produce price: $2.50-$6.00 per kg for everyday lines.",
    ])

    pdf.sub_title("Dairy, Eggs & Chilled")
    pdf.body(
        "We stock a comprehensive chilled range from major brands and local producers, with a "
        "strong emphasis on free-range eggs and locally made dairy products."
    )
    pdf.bullet([
        "Full-cream, skim, reduced-fat, lactose-free, and plant-based milks.",
        "Yoghurts: Greek, natural, flavoured, and probiotic ranges.",
        "Cheeses: over 80 varieties including Australian, French, Italian, and Swiss.",
        "Free-range and organic eggs from Victorian farms; 12-packs from $5.50.",
        "Butter, cream, sour cream, ricotta, mascarpone, and specialty spreads.",
        "Ready-to-eat meals, marinated meats, dips, and charcuterie boards.",
    ])

    pdf.sub_title("Meat & Seafood")
    pdf.body(
        "All beef and lamb sold at FreshMart is sourced from Meat Standards Australia (MSA) "
        "accredited farms. Our seafood is sourced from Marine Stewardship Council (MSC) certified "
        "fisheries where possible."
    )
    pdf.bullet([
        "MSA-graded beef: scotch fillet, sirloin, rump, eye fillet, and more.",
        "Free-range chicken from Hazeldene's Chicken Farm, Victoria.",
        "Lamb: chops, shoulder, rack, and leg cuts.",
        "Pork: bacon, sausages, ribs, and roasting cuts.",
        "Fresh seafood: Atlantic salmon, barramundi, prawns, calamari, mussels, and oysters.",
        "Deli counter: made-to-order servings, sliced meats, and house-made marinades.",
    ])

    pdf.sub_title("Bakery & Deli")
    pdf.body(
        "Our in-store bakery bakes fresh bread daily from 5 am. The deli counter serves house-made "
        "salads, antipasto, and a rotating hot food offering from 11 am to 7 pm."
    )
    pdf.bullet([
        "Sourdough, rye, wholegrain, ciabatta, baguettes, rolls, and gluten-free loaves.",
        "Pastries: croissants, scrolls, danishes, and muffins baked fresh each morning.",
        "Custom celebration cakes: order 48 hours in advance at the deli counter.",
        "Deli salads: 12 rotating varieties including pasta, grain, and green salads.",
        "Hot food bar: roast chicken, quiches, pies, and a vegetarian option daily.",
        "Sliced meats: leg ham, salami, pastrami, turkey breast, and specialty smallgoods.",
    ])

    pdf.sub_title("Pantry & Grocery")
    pdf.body(
        "Our pantry range covers everyday essentials as well as specialty and international foods. "
        "We stock FreshMart Home Brand products at 20-35% below comparable branded lines."
    )
    pdf.bullet([
        "FreshMart Home Brand: 450+ products across pantry, cleaning, and personal care.",
        "International foods aisle: Asian, Middle Eastern, European, and South American products.",
        "Health food section: gluten-free, vegan, keto, and allergen-friendly ranges.",
        "Bulk dry goods: nuts, grains, legumes, dried fruits, and spices sold by weight.",
        "Condiments, sauces, oils, vinegars, canned goods, pasta, and rice.",
    ])

    pdf.sub_title("Beverages")
    pdf.body(
        "We carry an extensive range of alcoholic and non-alcoholic beverages. Our wine department "
        "is curated by a qualified sommelier and features over 400 labels."
    )
    pdf.bullet([
        "Soft drinks, sparkling water, juices, iced teas, energy drinks, and cordials.",
        "Coffee: whole bean, pre-ground, and pod formats from local Melbourne roasters.",
        "Beer: mainstream lagers, craft ales, IPAs, stouts, and imported beers.",
        "Wine: 400+ labels covering Australian, New Zealand, French, Italian, and Spanish wines.",
        "Spirits, liqueurs, and ready-to-drink cans.",
        "Non-alcoholic wine and beer options in every store.",
    ])

    pdf.sub_title("Household, Cleaning & Health")
    pdf.bullet([
        "Cleaning products: concentrated, eco-friendly, and conventional ranges.",
        "Laundry: powders, liquids, pods, and fabric softeners.",
        "Personal care: hair care, skin care, dental, and shaving.",
        "Baby: nappies, wipes, formula, and food pouches.",
        "Pet food and accessories for dogs, cats, fish, and small animals.",
        "Over-the-counter pharmacy: pain relief, vitamins, cold & flu, and first aid.",
    ])

    pdf.output(path)
    print(f"[freshmart] Written: {path}  ({Path(path).stat().st_size:,} bytes)")


def build_services_pdf(path: str) -> None:
    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_page()

    pdf.ln(6)
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(40, 120, 40)
    pdf.cell(0, 12, "FreshMart Grocery Co.", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(60, 60, 60)
    pdf.cell(0, 8, "Services, Loyalty Programme & Pricing Guide 2025",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    # FreshMart+ Loyalty Programme
    pdf.section_title("FreshMart+ Loyalty Programme")
    pdf.body(
        "The FreshMart+ Loyalty Card is free to join and available to any customer aged 16 or over. "
        "Card members earn 1 FreshPoint per $1 spent in store or online. Points can be redeemed as "
        "a discount at checkout (100 points = $1 off). Members also receive exclusive member prices, "
        "early access to sales, and personalised weekly specials."
    )
    pdf.sub_title("Membership Tiers")
    pdf.bullet([
        "Green (0-499 points/year): Member pricing on 300+ weekly items. Birthday bonus: 200 points.",
        "Silver (500-1,999 points/year): All Green benefits + free home delivery once per month "
        "+ 10% off FreshMart Home Brand products. Birthday bonus: 500 points.",
        "Gold (2,000+ points/year): All Silver benefits + 5% off total shop every visit "
        "+ dedicated phone support line + priority delivery slots. Birthday bonus: 1,000 points.",
    ])
    pdf.body(
        "Points expire 24 months after earning if no activity on the account. Points cannot be "
        "transferred between accounts. Family accounts (up to 4 cards linked) pool points into a "
        "single balance."
    )

    # Home Delivery
    pdf.section_title("Home Delivery")
    pdf.body(
        "FreshMart delivers to all suburbs within 20 km of a store. Orders can be placed via the "
        "FreshMart app or website (freshmart.co/order) and are picked from the nearest store. "
        "Same-day delivery is available for orders placed before 11 am Monday to Saturday."
    )
    pdf.sub_title("Delivery Fees")
    pdf.price_header(("Order Value", "Standard Fee", "Express Fee", "Gold Member"))
    pdf.price_row("Under $50", "$9.95", "Next 2-hr slot", "$6.95")
    pdf.price_row("$50 - $99.99", "$5.95", "+$4.00 surcharge", "$3.95")
    pdf.price_row("$100 - $149.99", "$3.95", "+$4.00 surcharge", "$1.95")
    pdf.price_row("$150 and over", "FREE", "+$4.00 surcharge", "FREE")
    pdf.ln(2)
    pdf.bullet([
        "Delivery windows: 2-hour slots from 8 am to 8 pm, 7 days a week.",
        "Express delivery (1-hour): available in selected suburbs, subject to availability.",
        "Live order tracking via the FreshMart app from the moment picking begins.",
        "Substitutions policy: if an item is unavailable, we substitute with an equal or higher-"
        "value product at no extra charge, or issue a full refund for that item.",
        "Minimum order value: $30 for home delivery.",
        "Contactless delivery option: leave at door with a photo confirmation.",
    ])

    # Click & Collect
    pdf.section_title("Click & Collect")
    pdf.body(
        "Order online and collect from any of our 12 stores. Click & Collect orders are ready "
        "within 2 hours of placement during store opening hours. Collection is free on all orders."
    )
    pdf.bullet([
        "Free on all order sizes - no minimum spend.",
        "Ready in 2 hours (during store hours); next morning for orders placed after 6 pm.",
        "Collect from a dedicated Click & Collect counter - no queuing with in-store shoppers.",
        "Store your order for up to 24 hours in our temperature-controlled holding bays.",
        "Modify or cancel your order up to 1 hour before your nominated collection time.",
    ])

    # Pricing & Weekly Specials
    pdf.section_title("Pricing & Weekly Specials")
    pdf.body(
        "FreshMart runs weekly specials on 200+ products every Wednesday through Tuesday. "
        "Half-price specials, 2-for-1 deals, and multi-buy discounts are available in store and "
        "online. Loyalty card members receive an additional 50 exclusive member-only specials each week."
    )
    pdf.sub_title("Sample Everyday Produce Prices (standard, non-promotional)")
    pdf.price_header(("Product", "Regular Price", "Unit", "Loyalty Price"))
    pdf.price_row("Bananas (Cavendish)", "$2.90", "per kg", "$2.50")
    pdf.price_row("Broccoli", "$3.50", "each (approx 400g)", "$2.99")
    pdf.price_row("Loose Carrots", "$1.99", "per kg", "$1.50")
    pdf.price_row("Strawberries (250g punnet)", "$4.50", "per punnet", "$3.50")
    pdf.price_row("Roma Tomatoes", "$4.99", "per kg", "$3.99")
    pdf.price_row("Baby Spinach (120g)", "$3.50", "per bag", "$2.99")
    pdf.price_row("Avocado", "$1.99", "each", "$1.50")
    pdf.price_row("Sweet Potato", "$3.99", "per kg", "$3.00")
    pdf.ln(2)

    pdf.sub_title("Sample Dairy & Eggs Prices")
    pdf.price_header(("Product", "Regular Price", "Unit", "Loyalty Price"))
    pdf.price_row("Full Cream Milk (2L)", "$3.80", "per bottle", "$3.20")
    pdf.price_row("Oat Milk (1L)", "$4.50", "per carton", "$3.80")
    pdf.price_row("Free Range Eggs (12pk)", "$7.50", "per dozen", "$6.50")
    pdf.price_row("Greek Yoghurt (500g)", "$5.00", "per tub", "$4.20")
    pdf.price_row("Cheddar Cheese (500g)", "$8.50", "per block", "$7.20")
    pdf.price_row("Unsalted Butter (250g)", "$5.20", "per block", "$4.50")
    pdf.ln(2)

    # Corporate & Bulk Orders
    pdf.section_title("Corporate & Bulk Ordering")
    pdf.body(
        "FreshMart supplies offices, schools, aged care facilities, event caterers, and small "
        "businesses with regular grocery orders. Our corporate accounts team offers tailored "
        "pricing, scheduled standing orders, and a dedicated account manager for accounts "
        "spending over $1,000 per month."
    )
    pdf.bullet([
        "Corporate accounts: apply online at freshmart.co/corporate. Approval within 2 business days.",
        "Standing orders: set a recurring weekly or fortnightly order with automatic processing.",
        "Volume discounts: 5% off orders over $500; 10% off orders over $1,500 (net pricing).",
        "Invoiced billing: 30-day payment terms for approved corporate accounts.",
        "Dedicated account manager for accounts above $1,000 per month.",
        "Bulk pack options for pantry staples: rice, pasta, flour, oil, and cleaning supplies.",
        "Chilled and frozen bulk orders available with priority refrigerated delivery.",
    ])

    # Store Hours & Locations
    pdf.section_title("Store Hours & Key Locations")
    pdf.body(
        "All FreshMart stores are open 7 days a week. Standard hours apply to most locations; "
        "extended and reduced hours apply at selected stores. Check the FreshMart app for your "
        "nearest store's exact hours."
    )
    pdf.sub_title("Standard Store Hours")
    pdf.bullet([
        "Monday to Friday: 7:00 am - 10:00 pm",
        "Saturday: 7:00 am - 10:00 pm",
        "Sunday: 8:00 am - 9:00 pm",
        "Public holidays: 9:00 am - 6:00 pm (Christmas Day closed)",
    ])
    pdf.sub_title("Select Store Details")
    pdf.bullet([
        "Fitzroy (Flagship): 142 Smith Street, Fitzroy VIC 3065. Ph: (03) 9415 1200.",
        "Carlton: 280 Lygon Street, Carlton VIC 3053. Ph: (03) 9347 8800.",
        "South Yarra: 501 Chapel Street, South Yarra VIC 3141. Ph: (03) 9826 4400.",
        "Box Hill: 18 Main Street, Box Hill VIC 3128. Ph: (03) 9899 7700.",
        "Footscray: 165 Hopkins Street, Footscray VIC 3011. Ph: (03) 9687 3300.",
    ])

    # Returns & Freshness Guarantee
    pdf.section_title("Freshness Guarantee & Returns Policy")
    pdf.body(
        "FreshMart guarantees the freshness of all perishable products. If any item does not meet "
        "your expectations, return it to any store or contact us online for a full refund or "
        "replacement - no questions asked."
    )
    pdf.bullet([
        "Bring the item (or its packaging) to any FreshMart store for an immediate exchange or refund.",
        "Online purchases: use the FreshMart app to report an issue within 48 hours of delivery.",
        "Refunds credited to original payment method within 3-5 business days.",
        "Non-perishables: returned within 30 days in original condition for a full refund.",
        "Change-of-mind returns on non-food items accepted within 14 days with receipt.",
    ])

    # Contact
    pdf.section_title("Contact Us")
    pdf.bullet([
        "Customer service: hello@freshmart.co  |  1800 FRESH MART (1800 373 746)",
        "Live chat: available on the FreshMart app and website, 8 am - 8 pm daily.",
        "Corporate sales: corporate@freshmart.co",
        "Media enquiries: media@freshmart.co",
        "Head office: 142 Smith Street, Fitzroy VIC 3065",
        "Website: freshmart.co  |  App: available on iOS and Android",
    ])

    pdf.output(path)
    print(f"[freshmart] Written: {path}  ({Path(path).stat().st_size:,} bytes)")


if __name__ == "__main__":
    RESOURCES.mkdir(parents=True, exist_ok=True)
    build_overview_pdf(str(RESOURCES / "freshmart_overview.pdf"))
    build_services_pdf(str(RESOURCES / "freshmart_services_pricing.pdf"))
