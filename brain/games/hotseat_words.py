"""Hot Seat's categories: what the host says, and the answers it accepts without asking
anyone. An answer not listed goes to the talk model, or counts when there is none
(brain/games/hotseat.py). Standard library only: the referee imports it."""

from __future__ import annotations

# key: (what the host says, the accepted answers)
CATEGORIES: dict[str, tuple[str, tuple[str, ...]]] = {
    "fruits": ("Fruits", (
        "apple", "banana", "orange", "grape", "strawberry", "blueberry", "raspberry", "blackberry", "cherry",
        "peach", "pear", "plum", "apricot", "mango", "pineapple", "papaya", "kiwi", "watermelon", "melon",
        "cantaloupe", "honeydew", "lemon", "lime", "grapefruit", "tangerine", "clementine", "mandarin", "coconut",
        "pomegranate", "fig", "date", "lychee", "guava", "passion fruit", "dragon fruit", "persimmon", "nectarine",
        "cranberry", "avocado", "tomato", "olive", "starfruit", "jackfruit", "durian", "kumquat", "quince",
        "gooseberry", "currant", "raisin", "prune", "plantain", "boysenberry", "elderberry", "mulberry",
    )),
    "animals": ("Animals", (
        "dog", "cat", "horse", "cow", "pig", "sheep", "goat", "chicken", "duck", "goose", "turkey", "rabbit",
        "mouse", "rat", "hamster", "lion", "tiger", "bear", "wolf", "fox", "deer", "moose", "elk", "elephant",
        "giraffe", "zebra", "hippo", "rhino", "monkey", "gorilla", "chimpanzee", "kangaroo", "koala", "panda",
        "penguin", "eagle", "owl", "hawk", "parrot", "pigeon", "crow", "snake", "lizard", "frog", "turtle",
        "crocodile", "alligator", "shark", "whale", "dolphin", "octopus", "squid", "crab", "lobster", "fish",
        "salmon", "bee", "ant", "spider", "butterfly", "camel", "llama", "alpaca", "sloth", "otter", "beaver",
        "raccoon", "skunk", "squirrel", "bat", "cheetah", "leopard", "jaguar", "hyena", "seal", "walrus",
        "flamingo", "peacock", "swan", "donkey", "mule", "bison", "buffalo", "hedgehog", "porcupine", "badger",
    )),
    "countries": ("Countries", (
        "united states", "usa", "america", "canada", "mexico", "brazil", "argentina", "chile", "peru", "colombia",
        "venezuela", "cuba", "jamaica", "england", "united kingdom", "uk", "scotland", "ireland", "wales",
        "france", "spain", "portugal", "italy", "germany", "netherlands", "holland", "belgium", "switzerland",
        "austria", "poland", "sweden", "norway", "denmark", "finland", "iceland", "greece", "turkey", "russia",
        "ukraine", "egypt", "morocco", "nigeria", "kenya", "ethiopia", "south africa", "ghana", "china",
        "japan", "korea", "south korea", "north korea", "india", "pakistan", "thailand", "vietnam",
        "philippines", "indonesia", "malaysia", "singapore", "australia", "new zealand", "israel", "iran",
        "iraq", "saudi arabia", "qatar", "nepal", "mongolia", "taiwan", "cambodia", "laos", "czech republic",
        "hungary", "romania", "bulgaria", "croatia", "serbia", "afghanistan", "bangladesh", "sri lanka",
    )),
    "colors": ("Colors", (
        "red", "orange", "yellow", "green", "blue", "purple", "violet", "indigo", "pink", "brown", "black",
        "white", "gray", "grey", "silver", "gold", "beige", "tan", "maroon", "navy", "teal", "turquoise",
        "cyan", "magenta", "lavender", "lilac", "crimson", "scarlet", "burgundy", "coral", "salmon", "peach",
        "mint", "olive", "lime", "aqua", "ivory", "cream", "khaki", "charcoal", "mauve", "fuchsia", "amber",
        "bronze", "copper", "emerald", "ruby", "sapphire", "plum", "chartreuse", "periwinkle", "rose",
    )),
    "sports": ("Sports", (
        "soccer", "football", "basketball", "baseball", "softball", "tennis", "golf", "hockey", "volleyball",
        "rugby", "cricket", "lacrosse", "swimming", "diving", "running", "track", "boxing", "wrestling",
        "karate", "judo", "taekwondo", "fencing", "archery", "skiing", "snowboarding", "skating",
        "ice skating", "surfing", "skateboarding", "cycling", "rowing", "sailing", "badminton", "ping pong",
        "table tennis", "squash", "racquetball", "bowling", "gymnastics", "water polo", "handball", "polo",
        "climbing", "rock climbing", "marathon", "triathlon", "curling", "bobsled", "pickleball", "dodgeball",
        "kickball", "darts", "billiards", "pool", "equestrian", "mma", "kayaking", "canoeing", "frisbee",
    )),
    "vegetables": ("Vegetables", (
        "carrot", "potato", "sweet potato", "onion", "garlic", "broccoli", "cauliflower", "cabbage", "lettuce",
        "spinach", "kale", "celery", "cucumber", "zucchini", "squash", "pumpkin", "eggplant", "pepper",
        "bell pepper", "jalapeno", "corn", "pea", "green bean", "bean", "asparagus", "artichoke", "beet",
        "radish", "turnip", "parsnip", "leek", "shallot", "scallion", "green onion", "mushroom", "brussels sprout",
        "okra", "yam", "arugula", "bok choy", "chard", "collard", "tomato", "avocado", "edamame", "chickpea",
        "lentil", "ginger", "fennel", "rutabaga", "kohlrabi", "watercress",
    )),
    "car brands": ("Car brands", (
        "toyota", "honda", "ford", "chevrolet", "chevy", "nissan", "hyundai", "kia", "mazda", "subaru",
        "volkswagen", "vw", "bmw", "mercedes", "mercedes benz", "audi", "porsche", "ferrari", "lamborghini",
        "maserati", "bugatti", "mclaren", "tesla", "jeep", "dodge", "chrysler", "ram", "gmc", "cadillac",
        "buick", "lincoln", "lexus", "acura", "infiniti", "volvo", "jaguar", "land rover", "range rover",
        "mini", "fiat", "alfa romeo", "peugeot", "renault", "citroen", "bentley", "rolls royce",
        "aston martin", "mitsubishi", "suzuki", "genesis", "rivian", "lucid", "polestar", "lotus", "pontiac",
        "saturn", "hummer", "skoda", "seat", "opel", "byd",
    )),
    "us states": ("US states", (
        "alabama", "alaska", "arizona", "arkansas", "california", "colorado", "connecticut", "delaware",
        "florida", "georgia", "hawaii", "idaho", "illinois", "indiana", "iowa", "kansas", "kentucky",
        "louisiana", "maine", "maryland", "massachusetts", "michigan", "minnesota", "mississippi", "missouri",
        "montana", "nebraska", "nevada", "new hampshire", "new jersey", "new mexico", "new york",
        "north carolina", "north dakota", "ohio", "oklahoma", "oregon", "pennsylvania", "rhode island",
        "south carolina", "south dakota", "tennessee", "texas", "utah", "vermont", "virginia", "washington",
        "west virginia", "wisconsin", "wyoming",
    )),
    "instruments": ("Musical instruments", (
        "guitar", "electric guitar", "bass", "bass guitar", "piano", "keyboard", "organ", "drum", "drums",
        "violin", "viola", "cello", "double bass", "harp", "flute", "piccolo", "clarinet", "oboe", "bassoon",
        "saxophone", "sax", "trumpet", "trombone", "tuba", "french horn", "horn", "harmonica", "accordion",
        "banjo", "ukulele", "mandolin", "xylophone", "marimba", "glockenspiel", "triangle", "tambourine",
        "cymbal", "bongo", "conga", "recorder", "bagpipes", "sitar", "synthesizer", "kazoo", "cowbell",
        "maracas", "didgeridoo", "theremin", "lute", "harpsichord", "steel drum", "timpani",
    )),
    "body parts": ("Body parts", (
        "head", "hair", "face", "eye", "eyebrow", "eyelash", "ear", "nose", "mouth", "lip", "tongue", "tooth",
        "teeth", "chin", "cheek", "jaw", "forehead", "neck", "throat", "shoulder", "arm", "elbow", "wrist",
        "hand", "finger", "thumb", "nail", "fingernail", "chest", "back", "stomach", "belly", "waist", "hip",
        "leg", "thigh", "knee", "shin", "calf", "ankle", "foot", "feet", "heel", "toe", "skin", "bone", "heart",
        "lung", "liver", "kidney", "brain", "spine", "rib", "muscle", "armpit", "belly button", "knuckle",
        "palm", "eyelid", "nostril", "skull", "pinky",
    )),
    "kitchen": ("Things in a kitchen", (
        "fridge", "refrigerator", "freezer", "oven", "stove", "microwave", "toaster", "dishwasher", "sink",
        "blender", "mixer", "kettle", "coffee maker", "pan", "frying pan", "pot", "spatula", "whisk", "ladle",
        "knife", "fork", "spoon", "plate", "bowl", "cup", "mug", "glass", "cutting board", "colander",
        "grater", "peeler", "rolling pin", "measuring cup", "oven mitt", "apron", "napkin", "paper towel",
        "sponge", "dish soap", "trash can", "cabinet", "drawer", "counter", "tongs", "can opener",
        "bottle opener", "corkscrew", "tupperware", "foil", "plastic wrap", "salt", "pepper", "spice rack",
        "chopsticks", "teapot", "air fryer", "rice cooker", "slow cooker", "baking sheet", "timer",
    )),
    "pizza toppings": ("Pizza toppings", (
        "pepperoni", "sausage", "mushroom", "onion", "pepper", "green pepper", "bell pepper", "olive",
        "black olive", "pineapple", "ham", "bacon", "chicken", "beef", "meatball", "anchovy", "spinach",
        "tomato", "basil", "garlic", "jalapeno", "cheese", "extra cheese", "mozzarella", "parmesan",
        "ricotta", "feta", "goat cheese", "artichoke", "arugula", "salami", "prosciutto", "pesto",
        "barbecue chicken", "buffalo chicken", "broccoli", "corn", "egg", "shrimp", "tuna", "chili flakes",
        "red pepper flakes", "oregano", "sun dried tomato", "eggplant", "zucchini", "kale", "hot honey",
    )),
    "breakfast": ("Breakfast foods", (
        "pancake", "waffle", "french toast", "toast", "bagel", "muffin", "croissant", "donut", "doughnut",
        "cereal", "oatmeal", "granola", "yogurt", "egg", "eggs", "scrambled eggs", "omelet", "omelette",
        "bacon", "sausage", "ham", "hash brown", "hash browns", "biscuit", "gravy", "grits", "fruit",
        "banana", "orange juice", "coffee", "tea", "milk", "smoothie", "breakfast burrito", "burrito",
        "eggs benedict", "avocado toast", "cinnamon roll", "scone", "crepe", "porridge", "quiche",
        "frittata", "breakfast sandwich", "english muffin", "danish", "chilaquiles", "congee", "shakshuka",
    )),
    "jobs": ("Jobs", (
        "doctor", "nurse", "teacher", "lawyer", "engineer", "firefighter", "police officer", "cop", "pilot",
        "chef", "cook", "waiter", "waitress", "bartender", "barista", "farmer", "plumber", "electrician",
        "carpenter", "mechanic", "dentist", "vet", "veterinarian", "pharmacist", "scientist", "astronaut",
        "artist", "musician", "singer", "actor", "actress", "writer", "author", "journalist", "photographer",
        "programmer", "developer", "accountant", "banker", "cashier", "librarian", "janitor", "soldier",
        "judge", "architect", "designer", "dancer", "coach", "athlete", "driver", "truck driver",
        "mail carrier", "mailman", "baker", "butcher", "surgeon", "therapist", "lifeguard", "tailor",
    )),
}

# Things heard that are nobody's answer: room noise, filler and giving up.
NOISE = frozenset({
    "oh", "uh", "um", "umm", "uhh", "hmm", "hm", "mm", "mhm", "ah", "eh", "er", "huh", "you", "okay", "ok",
    "so", "like", "well", "wait", "what", "yeah", "yes", "no", "thank", "thanks", "bye", "music", "applause",
    "laughter", "laughing",
})
GIVE_UP = (
    "i don't know", "i dont know", "don't know", "dont know", "no idea", "pass", "skip", "dunno",
    "i can't think", "i cant think", "nothing", "i give up", "give up", "i got nothing",
)
