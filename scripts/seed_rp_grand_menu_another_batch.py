from __future__ import annotations

"""
Create/update Hotel RP Grand & Restaurants' menu.

The printed menu price is treated as the seller transfer price:
    display price = transfer price + 30%
    MRP           = transfer price + 39%

Run on EC2 inside the backend container:
    docker compose exec backend python -m scripts.seed_rp_grand_menu

Preview without changing the database:
    docker compose exec backend python -m scripts.seed_rp_grand_menu --dry-run
"""

import argparse
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func

from app.core.database import SessionLocal

# Register every mapper the same way app.main does.
from app.modules.superadmin.models import Tenant, DeliveryZone, DeliveryException  # noqa: F401
from app.modules.users.models import User, CustomerProfile, Address, CustomerSettings  # noqa: F401
from app.modules.otp.models import OTP  # noqa: F401
from app.modules.restaurants.models import (
    CatalogCategory,
    CatalogSubcategory,
    Restaurant,
    MenuCategory,
    MenuItem,
    MenuItemVariant,
)
from app.modules.orders.models import Order, OrderItem, DeliveryProfile, DeliveryOffer  # noqa: F401
from app.modules.banners.models import HomeBannerSlide  # noqa: F401
from app.modules.payments.models import (
    PaymentSettings, RestaurantEarning, DeliveryEarning, Withdrawal, BankAccount
)  # noqa: F401
from app.modules.promocodes.models import PromoCode, PromoCodeUsage  # noqa: F401
from app.modules.admin.models import ImpersonationSession  # noqa: F401
from app.modules.admin.reports.models import ReportDelivery  # noqa: F401
from app.modules.delivery_partner.models import DeliveryPartnerDetails  # noqa: F401


RESTAURANT_NAME = "Hotel RP Grand & Restaurants"
TENANT_SLUG = "lalganj"
DISPLAY_MARKUP = Decimal("1.30")
MRP_MARKUP = Decimal("1.39")
MONEY = Decimal("0.01")


SUBCATEGORIES = {
    "south-indian": "South Indian",
    "soup": "Soup",
    "papad": "Papad",
    "snacks": "Snacks",
    "pasta": "Pasta",
    "burger": "Burger",
    "sandwich": "Sandwich",
    "pizza": "Pizza",
    "rice-noodles": "Rice & Noodles",
    "chinese-starters": "Chinese Starters",
    "tandoori-starters": "Tandoori Starters",
    "paneer-delight": "Paneer Delight",
    "dal": "Dal",
    "main-course-veg": "Main Course Veg",
    "rice-biryani": "Rice & Biryani",
    "bread": "Bread",
    "raita": "Raita",
    "sweets-ice-cream": "Sweets & Ice Cream",
    "thali": "Traditional Thali Platters",
}


@dataclass(frozen=True)
class Variant:
    label: str
    transfer_price: Decimal


@dataclass(frozen=True)
class MenuRow:
    name: str
    description: str
    subcategory_slug: str
    variants: tuple[Variant, ...]


def variants(*pairs: tuple[str, str]) -> tuple[Variant, ...]:
    return tuple(Variant(label, Decimal(price)) for label, price in pairs)


def single(price: str) -> tuple[Variant, ...]:
    return variants(("Regular", price))


def item(
    name: str,
    description: str,
    transfer_price: str,
    subcategory_slug: str,
) -> MenuRow:
    return MenuRow(name, description, subcategory_slug, single(transfer_price))


def item_named(
    name: str,
    description: str,
    subcategory_slug: str,
    *price_labels: tuple[str, str],
) -> MenuRow:
    return MenuRow(
        name=name,
        description=description,
        subcategory_slug=subcategory_slug,
        variants=variants(*price_labels),
    )


# 3-4 word descriptions are used where the printed menu has no description.
# Existing descriptions from the earlier breakfast seed are retained where applicable.
ITEMS = [
    # South Indian
    item("Plain Dosa", "Crispy plain rice crepe", "129", "south-indian"),
    item("Masala Dosa", "Crispy dosa with potato", "159", "south-indian"),
    item("Spicy Mysore Masala Dosa", "Spicy Mysore style dosa", "179", "south-indian"),
    item("Paneer Masala Dosa", "Paneer stuffed masala dosa", "179", "south-indian"),
    item("Cheesy Masala Dosa", "Cheesy dosa with potato", "199", "south-indian"),
    item("Rava Plain Dosa", "Crispy semolina dosa", "179", "south-indian"),
    item("Rava Masala Dosa", "Semolina dosa with potato", "199", "south-indian"),
    item("Rava Paneer Dosa", "Semolina dosa with paneer", "209", "south-indian"),
    item("Vada Sambar", "Crispy vada with sambar", "139", "south-indian"),
    item("Idli Sambar", "Soft idli with sambar", "139", "south-indian"),
    item("Onion Uttapam", "Soft uttapam with onions", "149", "south-indian"),
    item("Paneer Uttapam", "Soft uttapam with paneer", "189", "south-indian"),
    item("Mix Veg Uttapam", "Mixed vegetable topped uttapam", "179", "south-indian"),
    item("RP Grand Special Dosa", "Signature special stuffed dosa", "249", "south-indian"),

    # Soup
    item("Manchow Soup", "Spicy Indo Chinese soup", "139", "soup"),
    item("Hot & Sour Soup", "Tangy spicy vegetable soup", "149", "soup"),
    item("Sweet Corn Soup", "Creamy sweet corn soup", "149", "soup"),
    item("Veg Clear Soup", "Light clear vegetable soup", "149", "soup"),
    item("Lemon Coriander Soup", "Refreshing lemon coriander soup", "149", "soup"),
    item("Cream of Tomato", "Rich creamy tomato soup", "169", "soup"),

    # Papad
    item_named("Dry Papad Roasted / Fry", "Crispy roasted or fried papad", "papad",
               ("Roasted", "45"), ("Fry", "55")),
    item("Masala Papad", "Crispy papad with masala", "89", "papad"),
    item("Minat Masala", "Spiced papad with mint", "149", "papad"),

    # Snacks
    item_named("French Fries", "Crispy golden potato fries", "snacks",
               ("Regular", "99"), ("Medium", "109"), ("Large", "119")),
    item_named("Maggi Plain", "Classic plain Maggi noodles", "snacks",
               ("Half", "80"), ("Full", "150")),
    item_named("Tadka Maggi", "Spiced Maggi with tadka", "snacks",
               ("Half", "90"), ("Full", "170")),
    item_named("Spicy Schezwan Maggi", "Spicy Schezwan Maggi noodles", "snacks",
               ("Half", "90"), ("Full", "170")),
    item_named("Italian Cheese Maggi", "Cheesy Italian style Maggi", "snacks",
               ("Half", "100"), ("Full", "190")),
    item("Nachos", "Crispy nachos with toppings", "209", "snacks"),
    item("American Cheese Corn Ball", "Crispy cheesy corn balls", "249", "snacks"),
    item("Paneer Cutlet", "Crispy spiced paneer cutlet", "249", "snacks"),
    item("Mexican Cheese Cigar Roll", "Crispy Mexican cheese rolls", "279", "snacks"),
    item("Plain Garlic Bread", "Soft bread with garlic", "149", "snacks"),
    item("Cheese Garlic Bread", "Cheesy bread with garlic", "179", "snacks"),
    item("Mexican Cheese Garlic Bread", "Mexican cheesy garlic bread", "199", "snacks"),

    # Pasta
    item("Penne Alfredo Pasta (White)", "Creamy white Alfredo penne", "249", "pasta"),
    item("Penne Arrabiata Pasta(Red)", "Spicy red Arrabiata penne", "249", "pasta"),
    item("Penne Mix Sauce Pasta", "Creamy mixed sauce penne", "269", "pasta"),
    item("Mac & Cheese Pasta", "Creamy cheesy macaroni pasta", "289", "pasta"),

    # Burger
    item("Aloo Tikki Burger", "Crispy potato patty burger", "79", "burger"),
    item("Veg Burger", "Classic vegetable patty burger", "89", "burger"),
    item("Veg Cheese Burger", "Vegetable burger with cheese", "99", "burger"),
    item("Crunchy Paneer Burger", "Crispy paneer patty burger", "109", "burger"),
    item("RP Grand Special Burger", "Signature loaded special burger", "169", "burger"),

    # Sandwich
    item("Plain Veg Sandwich", "Fresh vegetable sandwich", "109", "sandwich"),
    item("Vegetable Grilld Sandwich", "Grilled vegetable sandwich", "149", "sandwich"),
    item("Vegetable Cheese Grilld Sandwich", "Grilled vegetable cheese sandwich", "169", "sandwich"),
    item("Paneer Tikka Sandwich", "Paneer tikka stuffed sandwich", "189", "sandwich"),
    item("American Corn Cheese Sandwich", "Corn and cheese sandwich", "199", "sandwich"),

    # Pizza
    item("Margherita Pizza", "Classic cheese tomato pizza", "209", "pizza"),
    item("Corn Delight Pizza", "Sweet corn topped pizza", "239", "pizza"),
    item("Onion Delight Pizza", "Fresh onion topped pizza", "239", "pizza"),
    item("Capsicum Delight Pizza", "Fresh capsicum topped pizza", "239", "pizza"),
    item("OTC Pizza (Onion Tomato Capsicum)", "Onion tomato capsicum pizza", "269", "pizza"),
    item("Paneer Tikka Pizza", "Paneer tikka topped pizza", "289", "pizza"),
    item("Chilli Paneer Pizza", "Spicy chilli paneer pizza", "299", "pizza"),
    item("Mushroom Chilli Pizza", "Spicy mushroom chilli pizza", "299", "pizza"),
    item("Farm House Pizza", "Loaded garden vegetable pizza", "289", "pizza"),
    item("RP Grand Special Pizza", "Signature loaded special pizza", "309", "pizza"),

    # Rice & Noodles
    item_named("Veg Noodle", "Stir fried vegetable noodles", "rice-noodles",
               ("Half", "159"), ("Full", "259")),
    item_named("Hakka Noodle", "Classic stir fried hakka noodles", "rice-noodles",
               ("Half", "159"), ("Full", "259")),
    item_named("Chilli Garlic Noodle", "Spicy chilli garlic noodles", "rice-noodles",
               ("Half", "179"), ("Full", "279")),
    item_named("Paneer Noodle", "Paneer tossed noodle preparation", "rice-noodles",
               ("Full", "279")),
    item_named("Veg Fried Rice", "Stir fried vegetable rice", "rice-noodles",
               ("Half", "179"), ("Full", "279")),
    item_named("Paneer Fried Rice", "Paneer tossed fried rice", "rice-noodles",
               ("Full", "289")),
    item_named("Schezwan Fried Rice", "Spicy Schezwan fried rice", "rice-noodles",
               ("Full", "289")),
    item_named("Spicy Maxican Fried Rice", "Spicy Mexican fried rice", "rice-noodles",
               ("Full", "299")),
    item_named("Schezwan Paneer Fried Rice", "Spicy paneer fried rice", "rice-noodles",
               ("Full", "299")),

    # Chinese Starters
    item_named("Veg Manchurian", "Crispy vegetable Manchurian", "chinese-starters",
               ("Dry", "219"), ("Gravy", "259")),
    item_named("Chilli Potato", "Crispy spicy chilli potato", "chinese-starters",
               ("Dry", "139"), ("Gravy", "219")),
    item_named("Honey Chilli Potato", "Sweet spicy chilli potato", "chinese-starters",
               ("Dry", "159"), ("Gravy", "249")),
    item_named("Paneer Chilli", "Spicy Indo Chinese paneer", "chinese-starters",
               ("Dry", "279"), ("Gravy", "299")),
    item_named("Mushroom Chilli", "Spicy chilli mushroom", "chinese-starters",
               ("Dry", "269"), ("Gravy", "289")),
    item_named("Paneer Dragon", "Spicy dragon style paneer", "chinese-starters",
               ("Dry", "289")),
    item_named("Schezwan Paneer", "Spicy Schezwan paneer", "chinese-starters",
               ("Dry", "289")),
    item_named("Veg Spring Roll", "Crispy vegetable spring rolls", "chinese-starters",
               ("Dry", "209")),
    item_named("Paneer Spring Roll", "Crispy paneer spring rolls", "chinese-starters",
               ("Dry", "229")),
    item_named("Salt & Pepper Corn", "Crispy seasoned sweet corn", "chinese-starters",
               ("Dry", "289")),
    item_named("Crispy Baby Corn", "Crispy seasoned baby corn", "chinese-starters",
               ("Dry", "279")),
    item_named("Paneer 65", "Crispy spicy paneer bites", "chinese-starters",
               ("Dry", "289")),

    # Tandoori Starters
    item("Veg Seek Kabab", "Grilled vegetable seek kebab", "239", "tandoori-starters"),
    item("Hara Bhara Kabab", "Green vegetable kebab", "239", "tandoori-starters"),
    item("Makhmali Kabab", "Soft creamy vegetable kebab", "259", "tandoori-starters"),
    item("Dahi Kabab", "Crispy hung curd kebab", "249", "tandoori-starters"),
    item("Dahi ke Soley", "Crispy spiced curd bites", "249", "tandoori-starters"),
    item("Paneer Tikka", "Chargrilled spiced paneer", "279", "tandoori-starters"),
    item("Paneer Malai Tikka", "Creamy chargrilled paneer", "289", "tandoori-starters"),
    item("Paneer Achari Tikka", "Pickle spiced paneer tikka", "279", "tandoori-starters"),
    item("Paneer Afghani Tikka", "Creamy Afghani paneer tikka", "299", "tandoori-starters"),
    item("Tandoori Soya Chap", "Smoky grilled soya chaap", "279", "tandoori-starters"),
    item("Stuffed Mushrooms Tikka", "Stuffed grilled mushroom tikka", "269", "tandoori-starters"),
    item("Tandoori Mushroom Tikka", "Smoky tandoori mushroom tikka", "259", "tandoori-starters"),
    item("Lahsini Paneer Tikka", "Garlic flavored paneer tikka", "289", "tandoori-starters"),

    # Paneer Delight
    item_named("Kadhai Paneer", "Spicy paneer with peppers", "paneer-delight",
               ("Half", "209"), ("Full", "219")),
    item_named("Paneer Butter Masala", "Creamy buttery paneer curry", "paneer-delight",
               ("Half", "209"), ("Full", "319")),
    item_named("Palak Paneer", "Creamy spinach paneer curry", "paneer-delight",
               ("Half", "209"), ("Full", "319")),
    item_named("Matar Paneer", "Peas cooked with paneer", "paneer-delight",
               ("Half", "209"), ("Full", "319")),
    item_named("Handi Paneer", "Rich handi style paneer", "paneer-delight",
               ("Half", "209"), ("Full", "319")),
    item("Paneer Tikka Masala", "Tandoori paneer in gravy", "329", "paneer-delight"),
    item("Shahi Paneer", "Rich creamy royal paneer", "329", "paneer-delight"),
    item("Paneer Lababdar", "Creamy tangy paneer gravy", "329", "paneer-delight"),
    item("Paneer Khurchan", "Spiced shredded paneer preparation", "319", "paneer-delight"),
    item("Paneer Changezi", "Rich spicy Changezi paneer", "319", "paneer-delight"),
    item("Paneer Maharaja", "Royal rich paneer curry", "319", "paneer-delight"),
    item("Mataka Paneer", "Clay pot style paneer", "319", "paneer-delight"),
    item("Paneer Kaleji", "Spiced paneer kaleji style", "329", "paneer-delight"),
    item("(Special) RP Grand Special Paneer Angara", "Smoky special paneer curry", "349", "paneer-delight"),
    item("(Special) Matar Methi Malai Paneer", "Creamy peas fenugreek paneer", "329", "paneer-delight"),

    # Dal
    item_named("Dal Tadka", "Yellow lentils with tadka", "dal",
               ("Half", "149"), ("Full", "239")),
    item_named("Dal Fry", "Creamy tempered yellow dal", "dal",
               ("Half", "159"), ("Full", "249")),
    item("Dal Dhaba", "Rustic dhaba style dal", "239", "dal"),
    item("Dal Makhni", "Creamy slow cooked black dal", "289", "dal"),
    item("Panchmel Dal", "Five lentil mixed dal", "289", "dal"),
    item("Lehsuni Dal Tadka", "Garlic tempered lentil dal", "249", "dal"),

    # Main Course Veg
    item_named("Mix Veg", "Mixed vegetables in rich gravy", "main-course-veg",
               ("Half", "189"), ("Full", "289")),
    item_named("Mushroom Matar", "Mushroom peas rich gravy", "main-course-veg",
               ("Half", "189"), ("Full", "299")),
    item_named("Veg Jaipuri", "Spiced Jaipuri mixed vegetables", "main-course-veg",
               ("Half", "189"), ("Full", "299")),
    item_named("Veg Kolhapuri", "Spicy Kolhapuri vegetable curry", "main-course-veg",
               ("Half", "189"), ("Full", "299")),
    item_named("Veg Jalfrezi", "Tangy mixed vegetable curry", "main-course-veg",
               ("Half", "189"), ("Full", "299")),
    item_named("Mushroom Do Pyaza", "Mushroom onion rich curry", "main-course-veg",
               ("Half", "189"), ("Full", "299")),
    item("Mushroom Tikka Masala", "Tandoori mushroom in gravy", "299", "main-course-veg"),
    item("Corn Palak", "Corn cooked in spinach", "299", "main-course-veg"),
    item("Deewani Handi", "Mixed vegetable handi curry", "299", "main-course-veg"),
    item("Veg Kofta", "Vegetable kofta in gravy", "269", "main-course-veg"),
    item("Aloo Dum Banarasi", "Banarasi style spiced potatoes", "289", "main-course-veg"),
    item("Kaju Masala", "Cashew nuts in rich gravy", "319", "main-course-veg"),
    item("Shahi Malai Kofta", "Creamy royal vegetable kofta", "319", "main-course-veg"),
    item("Veg Sham Savera Kofta", "Spinach stuffed vegetable kofta", "299", "main-course-veg"),
    item("Veg Toofani", "Spicy mixed vegetable curry", "299", "main-course-veg"),
    item("Kaju Korma", "Creamy cashew vegetable curry", "319", "main-course-veg"),
    item("Dum Aloo Kashmiri", "Kashmiri style potato curry", "289", "main-course-veg"),
    item("Aloo Jeera", "Cumin tempered potato curry", "239", "main-course-veg"),
    item("Aloo Gobhi", "Potato cauliflower spiced curry", "289", "main-course-veg"),
    item("Bhindi Masala", "Spiced okra onion curry", "289", "main-course-veg"),
    item("Soya chap Roganjosh", "Rich Kashmiri soya curry", "309", "main-course-veg"),

    # Rice & Biryani
    item_named("Steam Rice", "Steamed aromatic basmati rice", "rice-biryani",
               ("Half", "109"), ("Full", "179")),
    item_named("Jeera Rice", "Cumin flavored basmati rice", "rice-biryani",
               ("Half", "149"), ("Full", "199")),
    item_named("Veg Pulao", "Fragrant mixed vegetable pulao", "rice-biryani",
               ("Half", "169"), ("Full", "229")),
    item("Veg Biryani", "Aromatic vegetable dum biryani", "319", "rice-biryani"),
    item("Paneer Tikka Biryani", "Paneer tikka dum biryani", "329", "rice-biryani"),
    item("Veg Hyderabadi Biryani", "Hyderabadi style veg biryani", "319", "rice-biryani"),
    item("Soya Chaap Biryani", "Soya chaap dum biryani", "319", "rice-biryani"),

    # Bread
    item_named("Tawa Roti (Plain/Butter)", "Fresh tawa wheat roti", "bread",
               ("Plain", "25"), ("Butter", "30")),
    item("Tandoori Roti", "Clay oven wheat roti", "20", "bread"),
    item("Butter Tandoori Roti", "Buttery tandoori wheat roti", "30", "bread"),
    item_named("Missi Roti (Plain/Onion)", "Gram flour spiced roti", "bread",
               ("Plain", "45"), ("Onion", "50")),
    item("Laccha Paratha", "Flaky layered Indian paratha", "45", "bread"),
    item("Pudina Paratha", "Mint flavored layered paratha", "50", "bread"),
    item("Mirchi Paratha", "Spicy chilli stuffed paratha", "50", "bread"),
    item("Plain Naan", "Soft classic tandoori naan", "50", "bread"),
    item("Butter Naan", "Soft buttery tandoori naan", "60", "bread"),
    item("Garlic Naan", "Garlic flavored tandoori naan", "70", "bread"),
    item("Cheese Naan", "Soft naan filled with cheese", "99", "bread"),
    item("Cheese Garlic Naan", "Cheesy naan with garlic", "109", "bread"),
    item_named("Stuffed Kurcha (Potato/Onion/Paneer)", "Stuffed tandoori Indian bread", "bread",
               ("Potato", "70"), ("Onion", "80"), ("Paneer", "90")),
    item(
        "Bread Basket",
        "2 Tandoori Roti, 1 Butter Naan, 1 Missi Roti, 1 Larcha Paratha, 1 Garlic Non",
        "199",
        "bread",
    ),

    # Raita
    item("Plain Curd", "Fresh chilled plain curd", "99", "raita"),
    item("Plain Raita", "Classic creamy yogurt raita", "99", "raita"),
    item("Veg Mix Raita", "Mixed vegetable yogurt raita", "129", "raita"),
    item("Cucumber Raita", "Cool cucumber yogurt raita", "129", "raita"),
    item("Boondi Raita", "Boondi mixed creamy raita", "129", "raita"),
    item("Pineapple Raita", "Sweet pineapple yogurt raita", "159", "raita"),
    item("Mix Fruit Raita", "Fruity mixed yogurt raita", "159", "raita"),

    # Sweets & Ice Cream
    item_named("Gulab Jamun", "Warm syrupy gulab jamun", "sweets-ice-cream",
               ("1 Pc", "35"), ("2 Pc", "60")),
    item_named("Ras Malai", "Soft creamy ras malai", "sweets-ice-cream",
               ("1 Pc", "40"), ("2 Pc", "70")),
    item_named("Vanilla Ice Cream", "Classic creamy vanilla ice cream", "sweets-ice-cream",
               ("Half", "40"), ("Full", "70")),
    item_named("Mango Ice Cream", "Creamy refreshing mango ice cream", "sweets-ice-cream",
               ("Half", "45"), ("Full", "80")),
    item_named("Butterscotch Ice Cream", "Crunchy creamy butterscotch ice cream", "sweets-ice-cream",
               ("Half", "45"), ("Full", "80")),
    item_named("Strawberry Ice Cream", "Creamy strawberry flavored ice cream", "sweets-ice-cream",
               ("Half", "45"), ("Full", "80")),
    item_named("Mix Fruit Ice Cream", "Fruity mixed ice cream", "sweets-ice-cream",
               ("Half", "50"), ("Full", "90")),
    item_named("Kesar Pista Ice Cream", "Saffron pistachio creamy ice cream", "sweets-ice-cream",
               ("Half", "50"), ("Full", "90")),
    item_named("Mix Badam Ice Cream", "Creamy almond flavored ice cream", "sweets-ice-cream",
               ("Half", "50"), ("Full", "90")),
    item_named("American Nut Ice Cream", "Crunchy nut flavored ice cream", "sweets-ice-cream",
               ("Half", "50"), ("Full", "90")),
    item("Chocolate Brownie", "Rich chocolate brownie dessert", "149", "sweets-ice-cream"),
    item("Sizzling Brownie With Ice Cream", "Sizzling brownie with ice cream", "219", "sweets-ice-cream"),
    item("RP Grand Special Sundae", "Signature loaded ice cream sundae", "269", "sweets-ice-cream"),

    # Traditional Thali Platters
    item("Deluxe Thali", "Complete deluxe Indian thali", "329", "thali"),
    item("RP Grand Special Thali", "Signature special Indian thali", "369", "thali"),
]


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def normalize_name(value: str) -> str:
    return " ".join((value or "").casefold().split())


def find_restaurant(db) -> Restaurant:
    tenant = db.query(Tenant).filter(Tenant.slug == TENANT_SLUG).one_or_none()
    if tenant is None:
        raise RuntimeError(f"Tenant with slug '{TENANT_SLUG}' was not found.")

    target = normalize_name(RESTAURANT_NAME)
    candidates = (
        db.query(Restaurant)
        .filter(
            Restaurant.tenant_id == tenant.id,
            Restaurant.name.ilike("%RP Grand%"),
        )
        .all()
    )
    matches = [row for row in candidates if normalize_name(row.name) == target]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise RuntimeError(
            f"Multiple restaurants matching '{RESTAURANT_NAME}' exist in tenant "
            f"'{TENANT_SLUG}'. Aborting to avoid changing the wrong restaurant."
        )

    names = ", ".join(f"#{row.id} {row.name!r}" for row in candidates) or "none"
    raise RuntimeError(
        f"Exact restaurant '{RESTAURANT_NAME}' was not found in tenant "
        f"'{TENANT_SLUG}'. Similar matches: {names}"
    )


def load_subcategories(db, restaurant: Restaurant) -> dict[str, CatalogSubcategory]:
    restaurant_category = (
        db.query(CatalogCategory)
        .filter(CatalogCategory.slug == "restaurant")
        .one_or_none()
    )
    if restaurant_category is None:
        restaurant_category = CatalogCategory(
            name="Restaurant",
            slug="restaurant",
            is_active=True,
            sort_order=1,
        )
        db.add(restaurant_category)
        db.flush()
    else:
        restaurant_category.is_active = True

    if restaurant.business_category_id is None:
        restaurant.business_category_id = restaurant_category.id
    elif restaurant.business_category_id != restaurant_category.id:
        raise RuntimeError(
            f"Restaurant #{restaurant.id} is not assigned to the Restaurant catalog category."
        )

    required = {row.subcategory_slug for row in ITEMS}
    rows = (
        db.query(CatalogSubcategory)
        .filter(
            CatalogSubcategory.category_id == restaurant_category.id,
            CatalogSubcategory.slug.in_(required),
        )
        .all()
    )
    by_slug = {row.slug: row for row in rows}
    missing = sorted(required - by_slug.keys())
    next_order = max((row.sort_order or 0 for row in rows), default=0) + 1

    for slug in missing:
        subcategory = CatalogSubcategory(
            category_id=restaurant_category.id,
            name=SUBCATEGORIES[slug],
            slug=slug,
            sort_order=next_order,
            is_active=True,
        )
        next_order += 1
        db.add(subcategory)
        by_slug[slug] = subcategory

    for subcategory in by_slug.values():
        subcategory.is_active = True

    if missing:
        db.flush()
    return by_slug


def get_or_create_menu_category(
    db,
    restaurant_id: int,
    subcategory: CatalogSubcategory,
) -> MenuCategory:
    category = (
        db.query(MenuCategory)
        .filter(
            MenuCategory.restaurant_id == restaurant_id,
            func.lower(MenuCategory.name) == subcategory.name.lower(),
        )
        .one_or_none()
    )
    if category is None:
        category = MenuCategory(
            restaurant_id=restaurant_id,
            name=subcategory.name,
            is_active=True,
        )
        db.add(category)
        db.flush()
    else:
        category.is_active = True
    return category


def upsert_item(
    db,
    restaurant: Restaurant,
    row: MenuRow,
    subcategory: CatalogSubcategory,
) -> str:
    category = get_or_create_menu_category(db, restaurant.id, subcategory)

    matches = (
        db.query(MenuItem)
        .filter(
            MenuItem.restaurant_id == restaurant.id,
            func.lower(MenuItem.name) == row.name.lower(),
        )
        .all()
    )
    if len(matches) > 1:
        raise RuntimeError(
            f"Multiple menu items named {row.name!r} exist for restaurant "
            f"#{restaurant.id}. Aborting instead of guessing."
        )

    menu_item = matches[0] if matches else MenuItem(restaurant_id=restaurant.id)
    action = "updated" if matches else "created"

    menu_item.category_id = category.id
    menu_item.business_subcategory_id = subcategory.id
    menu_item.name = row.name
    menu_item.description = row.description
    menu_item.is_veg = True
    menu_item.is_available = True
    menu_item.is_deleted = False
    menu_item.deleted_at = None

    if not matches:
        menu_item.is_bestseller = False
        db.add(menu_item)
        db.flush()

    existing_variants = (
        db.query(MenuItemVariant)
        .filter(MenuItemVariant.menu_item_id == menu_item.id)
        .all()
    )
    by_label = {
        (v.label or "").casefold(): v
        for v in existing_variants
    }

    intended_labels = set()
    for sort_order, variant_data in enumerate(row.variants):
        label = variant_data.label
        transfer = variant_data.transfer_price
        display_price = money(transfer * DISPLAY_MARKUP)
        mrp = money(transfer * MRP_MARKUP)

        variant = by_label.get(label.casefold())
        if variant is None:
            variant = MenuItemVariant(
                menu_item_id=menu_item.id,
                label=label,
            )
            db.add(variant)

        variant.actual_price = money(transfer)
        variant.price = display_price
        variant.original_price = mrp
        variant.sort_order = sort_order
        variant.is_available = True
        variant.is_deleted = False
        intended_labels.add(label.casefold())

        print(
            f"{action:7} {row.name:<42} [{label:<8}] "
            f"transfer=₹{transfer:.2f} "
            f"display=₹{display_price:.2f} "
            f"MRP=₹{mrp:.2f} "
            f"[{subcategory.name}]"
        )

    # Retire stale variants so old sizes/options are not still shown.
    for variant in existing_variants:
        if (variant.label or "").casefold() not in intended_labels:
            variant.is_available = False
            variant.is_deleted = True

    # MenuItem's primary price uses the first intended transfer price.
    first = row.variants[0]
    menu_item.actual_price = money(first.transfer_price)
    menu_item.price = money(first.transfer_price * DISPLAY_MARKUP)
    menu_item.original_price = money(first.transfer_price * MRP_MARKUP)

    return action


def seed(dry_run: bool = False) -> None:
    if not ITEMS:
        raise RuntimeError("No menu items defined.")

    db = SessionLocal()
    try:
        restaurant = find_restaurant(db)
        subcategories = load_subcategories(db, restaurant)

        print(
            f"Restaurant: #{restaurant.id} {restaurant.name} "
            f"(tenant_id={restaurant.tenant_id})"
        )
        print(
            f"Pricing: display = transfer + 30%; "
            f"MRP = transfer + 39%; items={len(ITEMS)}"
        )

        created = 0
        updated = 0

        for row in ITEMS:
            action = upsert_item(
                db,
                restaurant,
                row,
                subcategories[row.subcategory_slug],
            )
            if action == "created":
                created += 1
            else:
                updated += 1

        if dry_run:
            db.rollback()
            print(f"DRY RUN: rolled back {created} create(s), {updated} update(s).")
        else:
            db.commit()
            print(f"Done: {created} item(s) created, {updated} item(s) updated.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print changes, then roll them back.",
    )
    args = parser.parse_args()
    seed(dry_run=args.dry_run)