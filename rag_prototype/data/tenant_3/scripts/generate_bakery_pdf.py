"""
generate_bakery_pdf.py -- Creates Grain & Glory Artisan Bakery knowledge base PDFs.
Run once: python generate_bakery_pdf.py
"""

from pathlib import Path

from fpdf import FPDF, XPos, YPos

RESOURCES = Path(__file__).parent.parent / "resources"


class PDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(160, 100, 30)
        self.cell(0, 8, "Grain & Glory Artisan Bakery  |  Menu & Services Guide  |  2025",
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
        self.ln(2)
        self.set_draw_color(200, 160, 80)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(3)
        self.set_text_color(0, 0, 0)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 6, f"Page {self.page_no()}  |  hello@grainandglory.com.au  |  grainandglory.com.au",
                  align="C")

    def section_title(self, title: str):
        self.ln(4)
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(160, 100, 30)
        self.cell(0, 8, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(160, 100, 30)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(3)
        self.set_text_color(0, 0, 0)

    def sub_title(self, title: str):
        self.ln(2)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(80, 60, 20)
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

    def menu_row(self, item, price, desc=""):
        self.set_font("Helvetica", "B", 10)
        self.cell(90, 6, item)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(160, 100, 30)
        self.cell(25, 6, price, align="R")
        self.set_text_color(0, 0, 0)
        if desc:
            self.set_font("Helvetica", "I", 9)
            self.set_text_color(80, 80, 80)
            self.cell(0, 6, f"   {desc}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self.set_text_color(0, 0, 0)
        else:
            self.ln(6)


def build_menu_pdf(path: str) -> None:
    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_page()

    # Cover
    pdf.ln(6)
    pdf.set_font("Helvetica", "B", 24)
    pdf.set_text_color(160, 100, 30)
    pdf.cell(0, 12, "Grain & Glory", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(80, 60, 20)
    pdf.cell(0, 8, "Artisan Bakery & Patisserie  |  Menu & Price List 2025",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    pdf.body(
        "Grain & Glory Artisan Bakery was founded in 2012 by head baker Sophie Renard in the "
        "heart of Fitzroy, Melbourne. Everything we make is crafted by hand using traditional "
        "methods: long-fermented sourdough, laminated pastry dough prepared fresh every morning, "
        "and celebration cakes built on recipes refined over 15 years of baking. We use "
        "stoneground flours from Australian heritage wheat varieties, local free-range eggs, "
        "and cultured Australian butter in everything we make."
    )

    # Breads
    pdf.section_title("Sourdough & Artisan Breads")
    pdf.body(
        "Our breads are slow-fermented for 18-24 hours using our house sourdough culture, "
        "which Sophie brought back from a two-year apprenticeship in Lyon, France. All loaves "
        "are baked in our stone-deck oven starting at 5 am. Whole loaves are available until "
        "sold out; sliced loaves are available by request with 24-hour notice."
    )

    for item, price, desc in [
        ("Classic Sourdough (800g)", "$14.00", "Open crumb, chewy crust, pure wheat starter"),
        ("Country Sourdough (1kg)", "$17.00", "15% rye blend, robust tang, excellent keeping"),
        ("Dark Rye & Caraway (700g)", "$15.00", "Dense, moist, pairs with smoked salmon or cheese"),
        ("Spelt & Honey (750g)", "$16.50", "Mild, slightly sweet, light golden crumb"),
        ("Seeded Bloomer (800g)", "$16.00", "Sunflower, pumpkin, sesame & linseed crust"),
        ("Einkorn White (700g)", "$17.50", "Heritage grain, nutty flavour, exceptional aroma"),
        ("Gluten-Free Loaf (600g)", "$14.50", "Certified GF facility, rice & tapioca base"),
        ("Focaccia (half tray)", "$12.00", "Rosemary & sea salt; seasonal toppings on weekends"),
        ("Ciabatta (single)", "$6.50", "Open crumb, olive oil, ideal for panini"),
        ("Baguette (single)", "$5.00", "French-style, baked twice daily - morning and noon"),
        ("Dinner Rolls (6-pack)", "$9.00", "Soft milk rolls or sourdough knot rolls"),
    ]:
        pdf.menu_row(item, price, desc)

    # Pastries & Viennoiserie
    pdf.section_title("Pastries & Viennoiserie")
    pdf.body(
        "Our viennoiserie is made with a laminated dough prepared fresh each morning using "
        "84% fat cultured butter. Croissants take three days to make: the starter enriched dough "
        "is prepared Tuesday for Thursday's bake. We bake a single batch daily - once it's gone, "
        "it's gone."
    )

    for item, price, desc in [
        ("Plain Butter Croissant", "$6.50", "Honey-coloured, 48 layers, classic French lamination"),
        ("Almond Croissant", "$7.50", "Frangipane-filled, sliced and rebaked, flaked almonds"),
        ("Pain au Chocolat", "$7.00", "Double Valrhona dark chocolate batons"),
        ("Ham & Gruyere Croissant", "$9.00", "Smoked leg ham, aged Gruyere, Dijon mustard"),
        ("Kouign-Amann (slice)", "$7.00", "Caramelised, flaky, Breton-style butter cake"),
        ("Twice-Baked Pistachio Croissant", "$8.50", "Pistachio cream, candied pistachios, icing sugar"),
        ("Cardamom Morning Bun", "$6.00", "Orange zest, cardamom sugar, rolled in cinnamon"),
        ("Canele (single)", "$5.50", "Bordeaux-style, dark caramel crust, vanilla custard centre"),
        ("Danish (fruit or custard)", "$6.50", "Laminated pastry, seasonal fruit or vanilla custard"),
        ("Eclair (chocolate or coffee)", "$8.00", "Choux pastry, Valrhona ganache or coffee creme"),
        ("Tarte aux Pommes (slice)", "$8.50", "Thin apple tart on puff pastry, calvados glaze"),
        ("Quiche Lorraine (slice)", "$9.50", "Gruyere, free-range egg, smoked bacon, shortcrust"),
        ("Spinach & Feta Filo Scroll", "$8.50", "House-made filo, organic spinach, Persian feta"),
        ("Seasonal Fruit Tart (individual)", "$9.00", "Creme patissiere, seasonal fruits, apricot glaze"),
    ]:
        pdf.menu_row(item, price, desc)

    # Cookies & Slices
    pdf.section_title("Biscuits, Cookies & Slices")
    pdf.body(
        "All biscuits and slices are made in-house. Many are available in gift boxes (6, 12, or "
        "24 pieces) for corporate gifts and occasions - please order 48 hours ahead."
    )

    for item, price, desc in [
        ("Dark Chocolate & Sea Salt Cookie", "$4.50", "Valrhona 70% discs, fleur de sel finish"),
        ("Brown Butter Hazelnut Cookie", "$4.50", "Nutella-style gianduja filling"),
        ("Lemon Shortbread (2-pack)", "$5.00", "Cultured butter, Meyer lemon zest, crunchy sugar"),
        ("ANZAC Biscuit (each)", "$3.50", "Golden syrup, rolled oats, coconut, thin & chewy"),
        ("Florentine (each)", "$5.50", "Almonds, glacé citrus peel, dark chocolate underside"),
        ("Brownie (slice)", "$7.00", "Fudgy 70% cocoa, sea salt, walnut optional"),
        ("Lamington (each)", "$4.50", "Fresh sponge, raspberry jam, desiccated coconut"),
        ("Caramel Slice", "$6.50", "Biscuit base, soft caramel, dark chocolate top"),
        ("Raspberry & Rosewater Friand", "$5.50", "Brown butter, almond meal, frozen raspberries"),
        ("Cinnamon Snail (scrolled bun)", "$5.50", "Ceylon cinnamon, brown butter, cream cheese glaze"),
        ("Mixed Cookie Box (6 pieces)", "$22.00", "Chef's selection, ideal for gifting"),
        ("Mixed Cookie Box (12 pieces)", "$40.00", "Perfect for office gifts or events"),
    ]:
        pdf.menu_row(item, price, desc)

    # Cafe & Drinks
    pdf.section_title("Cafe Counter & Drinks")
    pdf.body(
        "We serve Proud Mary Coffee, roasted in Collingwood. All milk-based drinks use whole "
        "milk as default; oat, soy, almond, and macadamia milks available at no extra charge. "
        "Eat in or take away - we have 20 seats inside and a footpath terrace seating 12."
    )

    for item, price, desc in [
        ("Espresso / Short Black", "$4.50", "Single or double; seasonal single-origin available"),
        ("Flat White / Latte / Cappuccino", "$6.00", "200ml or 280ml"),
        ("Oat Flat White", "$6.50", "Minor Figures oat milk, signature blend"),
        ("Filter Coffee (batch brew)", "$4.50", "Rotating single-origin, filter grind, black"),
        ("Hot Chocolate", "$6.50", "Valrhona cocoa powder, steamed milk, marshmallow optional"),
        ("Chai Latte", "$6.50", "House-spiced loose-leaf chai, not a powder"),
        ("Matcha Latte", "$7.00", "Ceremonial grade Uji matcha, steamed milk"),
        ("Freshly Squeezed OJ (250ml)", "$6.00", "Valencia oranges, squeezed to order"),
        ("Still / Sparkling Water (500ml)", "$3.50", ""),
        ("House Lemonade (glass)", "$5.50", "Meyer lemon, elderflower, sparkling water"),
    ]:
        pdf.menu_row(item, price, desc)

    pdf.body(
        "Dietary notes: GF = Gluten Free, DF = Dairy Free, V = Vegan, VG = Vegetarian. "
        "We use nuts (especially almonds and hazelnuts) throughout our kitchen. While we take "
        "allergen requests seriously, we cannot guarantee a nut-free environment. Please speak "
        "to a team member if you have a severe allergy."
    )

    pdf.output(path)
    print(f"[grain&glory] Written: {path}  ({Path(path).stat().st_size:,} bytes)")


def build_services_pdf(path: str) -> None:
    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_page()

    pdf.ln(6)
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(160, 100, 30)
    pdf.cell(0, 12, "Grain & Glory Artisan Bakery",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(80, 60, 20)
    pdf.cell(0, 8, "Custom Orders, Wholesale & Services Guide 2025",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    # Custom Cakes
    pdf.section_title("Custom Celebration Cakes")
    pdf.body(
        "Grain & Glory bakes a limited number of custom celebration cakes each week. All cakes "
        "are made to order using organic ingredients. Our head pâtissier, Luca Bianchi, trained "
        "at Le Cordon Bleu Paris and brings classic French structure to Australian flavour profiles. "
        "Minimum lead time is 7 days; during peak periods (October to January) we recommend "
        "booking 4-6 weeks ahead."
    )

    pdf.sub_title("Cake Bases & Flavours")
    pdf.bullet([
        "Vanilla Bean Sponge: classic Victorian sponge with Madagascan vanilla bean paste.",
        "Dark Chocolate Fudge: 72% cocoa sponge, dark ganache crumb coat.",
        "Lemon Elderflower: citrus sponge soaked with elderflower cordial syrup.",
        "Carrot & Walnut: spiced carrot sponge, cream cheese frosting, candied walnuts.",
        "Almond Raspberry: frangipane base, fresh raspberry compote between layers.",
        "Salted Caramel: brown butter sponge, Breton salted caramel filling.",
        "Seasonal Fruit (market-dependent): ask about availability when ordering.",
        "Gluten-Free options available for all base flavours (surcharge applies).",
    ])

    pdf.sub_title("Pricing by Serving Size")
    pdf.bullet([
        "6 servings (15 cm round, 2 layers): from $95",
        "10 servings (18 cm round, 3 layers): from $145",
        "16 servings (22 cm round, 3 layers): from $195",
        "24 servings (26 cm round, 3 layers): from $265",
        "40 servings (30 cm round, 3-4 layers): from $380",
        "Tiered cakes (2-tier): from $420 (serves 30-50 depending on configuration)",
        "Tiered cakes (3-tier): from $680 (serves 60-100 depending on configuration)",
        "Sheet cake (feeds 30-40, undecorated): from $180",
    ])

    pdf.sub_title("Inclusions & Surcharges")
    pdf.bullet([
        "All prices include smooth buttercream finish, fresh flower arrangement (seasonal), "
        "and a personalised message plaque.",
        "Fondant finish: +$30 (small) to +$80 (large).",
        "Sculpted/3D elements: quoted individually.",
        "Edible printed images: +$25.",
        "Gluten-free conversion: +$20 flat fee.",
        "Allergen-specific baking (nut-free, dairy-free): quoted individually; requires "
        "a dedicated bake session outside standard hours.",
        "Same-week orders (less than 7 days): 25% rush surcharge, subject to availability.",
    ])

    pdf.sub_title("Ordering Process")
    pdf.bullet([
        "Step 1: Submit an enquiry via grainandglory.com.au/custom-cakes or email cakes@grainandglory.com.au.",
        "Step 2: Our team responds within 24 hours (Mon-Fri) with a quote and flavour consultation.",
        "Step 3: Confirm order with 50% non-refundable deposit.",
        "Step 4: Final design approval via email 14 days before collection.",
        "Step 5: Collect from our Fitzroy bakery on the agreed date before 1 pm.",
        "Delivery available within 10 km of Fitzroy for $35 (refrigerated van).",
        "Remaining balance due at collection.",
    ])

    # Wholesale & Trade
    pdf.section_title("Wholesale & Trade Supply")
    pdf.body(
        "Grain & Glory supplies fresh bread and pastries to a select number of Melbourne cafes, "
        "restaurants, and delis. We operate on a capacity-limited wholesale model: we accept new "
        "wholesale partners only when our production schedule allows. Current wholesale partners "
        "include eight Melbourne cafes and two boutique delis."
    )

    pdf.sub_title("What We Supply")
    pdf.bullet([
        "Sourdough loaves: Classic, Country, Rye, and Seeded in full-loaf or half-loaf format.",
        "Croissants and Pain au Chocolat: supplied unbaked (par-baked) or fully baked.",
        "Seasonal pastries: variable; discussed monthly with each partner.",
        "Baguettes and ciabatta: minimum 12-unit order per variety per delivery.",
        "Biscuit boxes: available in 24-unit trade packs, branded or unbranded.",
        "Custom labelling available for wholesale bread products (minimum 6-month commitment).",
    ])

    pdf.sub_title("Wholesale Pricing & Terms")
    pdf.bullet([
        "Wholesale pricing is approximately 30-40% below retail, depending on volume and product.",
        "Minimum weekly order: $250 (net) to qualify for wholesale pricing.",
        "Payment terms: weekly invoice, 7-day payment period.",
        "Delivery: Tuesday, Thursday, and Saturday mornings before 8 am within 15 km of Fitzroy.",
        "Delivery fee: $20 per delivery run (waived for orders over $400).",
        "New wholesale applications: email wholesale@grainandglory.com.au with your business details "
        "and estimated weekly order volume.",
        "Trial period: 4-week trial at wholesale rates before full agreement is signed.",
    ])

    # Baking Workshops
    pdf.section_title("Baking Workshops & Classes")
    pdf.body(
        "Sophie and Luca run hands-on baking classes from the bakery kitchen on selected Sundays "
        "and Monday evenings (the bakery's quiet day). All classes are capped at 8 participants "
        "to ensure personal attention. Classes are popular and book out weeks in advance."
    )

    pdf.sub_title("Class Schedule & Pricing")
    pdf.bullet([
        "Introduction to Sourdough (3 hours, Sunday morning): $145 per person. "
        "Learn to maintain a starter, shape a loaf, and understand the fermentation schedule. "
        "Take home your own loaf and a jar of starter.",
        "Advanced Sourdough: Scoring & Inclusions (3 hours, Sunday morning): $165 per person. "
        "Prerequisite: Intro class or prior sourdough experience. Focus on decorative scoring, "
        "seeded loaves, and laminated inclusions (cheese, herbs, olives).",
        "Croissant Masterclass (4 hours, Sunday): $195 per person. "
        "Full lamination from scratch. Take home 6 croissants and the recipe sheet.",
        "Celebration Cake Decorating (3.5 hours, Monday evening): $175 per person. "
        "Buttercream techniques, palette knife textures, and fresh flower placement.",
        "Kids Baking Party (2 hours, Saturday afternoon, ages 7-12): $85 per child. "
        "Minimum 8 children, maximum 12. Includes apron, ingredients, and a loot bag.",
        "Corporate Team Baking Experience (3 hours, any weekday evening): $200 per person "
        "(minimum 8, maximum 20). Customised theme; includes grazing table and wine.",
    ])

    pdf.sub_title("Booking")
    pdf.bullet([
        "Book online: grainandglory.com.au/workshops",
        "Gift vouchers available for any class. Valid 12 months from purchase.",
        "Cancellation policy: full refund with 72 hours notice; credit note within 48 hours.",
        "Private class hire: exclusive use of the kitchen for groups of 6-8, from $1,200.",
    ])

    # Catering
    pdf.section_title("Catering & Event Orders")
    pdf.body(
        "We provide bread baskets, pastry platters, and grazing tables for private events, "
        "corporate morning teas, and product launches. All catering orders require a minimum of "
        "5 business days notice; peak-season orders require 2 weeks."
    )

    pdf.sub_title("Catering Options")
    pdf.bullet([
        "Bread basket (serves 8-10): mixed sourdough slices, baguette rounds, cultured butter, "
        "and a seasonal spread. $75.",
        "Morning tea pastry platter (serves 10): 6 croissants, 4 danishes, 4 scrolls, "
        "2 quiche slices. $160.",
        "Afternoon tea sweet platter (serves 10): 12 mixed biscuits, 6 slices, 6 friands, "
        "2 tarts. $175.",
        "Grazing table (serves 20-25): artisan breads, cured meats, cheeses, fruits, dips, "
        "olives, and sweet bites. $450-$600 depending on inclusions.",
        "Custom platters: designed collaboratively; contact events@grainandglory.com.au.",
        "Delivery within 15 km of Fitzroy: $45. Setup on-site: additional $80.",
    ])

    # Hours & Contact
    pdf.section_title("Hours, Location & Contact")
    pdf.sub_title("Bakery Hours")
    pdf.bullet([
        "Tuesday to Friday: 7:00 am - 3:00 pm",
        "Saturday: 7:00 am - 2:00 pm",
        "Sunday: 8:00 am - 1:00 pm (workshops only - retail sales limited)",
        "Monday: CLOSED (production and workshop day only)",
        "Public holidays: closed. Check Instagram @grainandglory for holiday trading hours.",
    ])

    pdf.sub_title("Location")
    pdf.bullet([
        "Grain & Glory Artisan Bakery",
        "218 Gertrude Street, Fitzroy VIC 3065",
        "Entry from Gertrude Street; customer parking available on Gore Street.",
        "Tram: Route 86 (Smith Street tram), stop 14 (Gertrude Street).",
        "The bakery is fully wheelchair accessible.",
    ])

    pdf.sub_title("Contact")
    pdf.bullet([
        "General enquiries: hello@grainandglory.com.au  |  (03) 9415 8822",
        "Custom cake orders: cakes@grainandglory.com.au",
        "Wholesale enquiries: wholesale@grainandglory.com.au",
        "Workshop bookings: grainandglory.com.au/workshops",
        "Catering & events: events@grainandglory.com.au",
        "Instagram: @grainandglory  |  Facebook: Grain & Glory Bakery",
        "Newsletter: subscribe at grainandglory.com.au for weekly specials and new menu items.",
    ])

    pdf.output(path)
    print(f"[grain&glory] Written: {path}  ({Path(path).stat().st_size:,} bytes)")


if __name__ == "__main__":
    RESOURCES.mkdir(parents=True, exist_ok=True)
    build_menu_pdf(str(RESOURCES / "grain_and_glory_menu.pdf"))
    build_services_pdf(str(RESOURCES / "grain_and_glory_services.pdf"))
