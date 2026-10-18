"""20 Questions' offline table: common things and the yes/no traits that tell them
apart. The game plays from this with no model at all, and when a model is online the
table still answers wherever it has the trait, so a secret never drifts.

A trait is a question the robot can ask, a hint it can give, and the words that tell
the code a player's question is about it ("does it live in the water?" -> water).
`anti` words ask the opposite ("is it real?" asks about `madeup`, answered the other
way round).

A thing is "spoken name | aliases | traits": a trait it has, "~trait" for sort of,
nothing for no. Standard library only (the referee runs this on the Pi).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Trait:
    key: str
    question: str  # what the robot asks
    hint: str  # what a hint says when the secret has it
    words: tuple[str, ...]  # phrases in a player's question that mean this trait
    anti: tuple[str, ...] = ()  # phrases that ask the opposite


def _t(key: str, question: str, hint: str, words: str, anti: str = "") -> Trait:
    split = lambda s: tuple(w.strip() for w in s.split(",") if w.strip())  # noqa: E731
    return Trait(key, question, hint, split(words), split(anti))


TRAITS: tuple[Trait, ...] = (
    _t("alive", "Is it alive?", "It's alive.", "alive, living, living thing, breathe, breathes", "dead"),
    _t("animal", "Is it an animal?", "It's an animal.", "animal, creature, critter"),
    _t("mammal", "Is it a mammal?", "It's a mammal.", "mammal"),
    _t("bird", "Is it a bird?", "It's a bird.", "bird, feathers"),
    _t("bug", "Is it a bug?", "It's a bug.", "bug, insect, creepy crawly"),
    _t("water", "Does it live in water?", "It lives in water.",
       "live in water, lives in water, live in the water, lives in the water, in the water, in water, underwater, "
       "swim, swims, ocean, sea, fish"),
    _t("pet", "Can you keep it as a pet?", "People keep it as a pet.", "pet"),
    _t("fly", "Can it fly?", "It can fly.", "fly, flies, flying, wings, in the air, in the sky"),
    _t("legs4", "Does it have four legs?", "It has four legs.", "four legs, 4 legs"),
    _t("eggs", "Does it lay eggs?", "It lays eggs.", "lay eggs, lays eggs, hatch, hatches"),
    _t("meat", "Does it eat meat?", "It eats meat.", "eat meat, eats meat, carnivore, hunt, hunts, eat other"),
    _t("danger", "Is it dangerous?", "It can be dangerous.", "dangerous, deadly, kill, hurt you, bite, scary", "safe"),
    _t("farm", "Would you find it on a farm?", "You'd find it on a farm.", "farm"),
    _t("big", "Is it bigger than a person?", "It's bigger than a person.",
       "big, bigger, large, larger, huge, giant, tall, taller"),
    _t("hand", "Can you hold it in one hand?", "You can hold it in one hand.",
       "small, smaller, tiny, little, hold it, in your hand, one hand, pocket, fit in"),
    _t("food", "Can you eat it?", "You can eat it.", "eat it, eat, edible, food, snack, meal, taste"),
    _t("drink", "Can you drink it?", "You can drink it.", "drink, liquid, beverage, sip"),
    _t("plant", "Is it a plant?", "It's a plant, more or less.", "plant, grow, grows, tree"),
    _t("fruitveg", "Is it a fruit or a vegetable?", "It's a fruit or a vegetable.", "fruit, vegetable, veggie, produce"),
    _t("sweet", "Is it sweet?", "It's sweet.", "sweet, sugar, sugary, dessert, candy"),
    _t("hotfood", "Is it usually eaten hot?", "It's usually hot.", "hot, warm, cooked, cook"),
    _t("electric", "Does it use electricity?", "It runs on electricity.",
       "electricity, electric, electronic, battery, batteries, plug, plugged, charge, power"),
    _t("screen", "Does it have a screen?", "It has a screen.", "screen, display"),
    _t("kitchen", "Would you find it in a kitchen?", "You'd find it in a kitchen.", "kitchen, cook with, cooking"),
    _t("house", "Would you find it in a house?", "You'd find it in a house.",
       "house, home, inside, indoors, in your room, bedroom, living room"),
    _t("bathroom", "Would you find it in a bathroom?", "You'd find it in a bathroom.", "bathroom"),
    _t("outside", "Is it usually outside?", "It's usually outside.", "outside, outdoors, outdoor"),
    _t("vehicle", "Is it a vehicle?", "It's a vehicle.", "vehicle, drive, ride, ride in, transport, transportation"),
    _t("wheels", "Does it have wheels?", "It has wheels.", "wheel, wheels"),
    _t("place", "Is it a place?", "It's a place.", "place, location, visit, go to, go there, building"),
    _t("person", "Is it a person or a character?", "It's a person or a character.",
       "person, human, character, someone, people, man, woman, guy, girl, boy, celebrity"),
    _t("madeup", "Is it made up?", "It's made up.", "fictional, made up, imaginary, fake, pretend, fantasy",
       "real, exist, exists"),
    _t("metal", "Is it made of metal?", "It's made of metal.", "metal, metallic, steel, iron"),
    _t("wood", "Is it made of wood?", "It's made of wood.", "wood, wooden"),
    _t("sport", "Is it used in a sport?", "It's used in a sport.", "sport, sports, athletic"),
    _t("wear", "Can you wear it?", "You can wear it.", "wear, wearing, clothing, clothes, put on"),
    _t("tool", "Is it a tool?", "It's a tool.", "tool, fix things, build things"),
    _t("soft", "Is it soft?", "It's soft.", "soft, fluffy, squishy, fuzzy, furry", "hard"),
    _t("sharp", "Is it sharp?", "It's sharp.", "sharp, pointy, cut"),
    _t("noise", "Does it make noise?", "It makes noise.", "noise, sound, sounds, loud"),
    _t("music", "Is it a musical instrument?", "It makes music.", "music, musical, instrument"),
    _t("school", "Would you find it at a school or an office?", "You'd find it at school or an office.",
       "school, office, classroom, desk"),
    _t("movie", "Is it from a movie, a show or a cartoon?", "It's from a movie, a show or a cartoon.",
       "movie, film, show, cartoon, tv show, anime, video game, comic"),
    _t("famous", "Is it famous?", "It's famous.", "famous, well known, celebrity"),
    _t("city", "Is it a city?", "It's a city.", "city, town"),
    _t("nature", "Is it part of nature?", "It's part of nature.", "nature, natural, wild, the wild",
       "man made, manmade, artificial"),
)

TRAIT = {t.key: t for t in TRAITS}

# Traits that say what kind of thing it is. When a model is online the table's answer
# wins on these even when the thing has no tag (an untagged pizza is not alive); on the
# others, an untagged thing may just be missing a tag, so the model's answer stands.
KINDS = frozenset(
    ("alive", "animal", "mammal", "bird", "bug", "food", "drink", "fruitveg", "vehicle", "place", "person",
     "madeup", "electric", "city", "music", "plant")
)


@dataclass(frozen=True)
class Thing:
    name: str  # how it is said: "a toaster", "Paris"
    aliases: tuple[str, ...]  # what a guess may call it, lower-case
    yes: frozenset[str]
    sort: frozenset[str]

    def answer(self, trait: str) -> str:
        """"yes", "sort of" or "no"."""
        if trait in self.yes:
            return "yes"
        if trait in self.sort:
            return "sort of"
        return "no"


_RAW = """
a dog | dog, puppy, doggy, doggie | alive animal mammal pet legs4 meat noise house outside ~farm ~soft
a cat | cat, kitten, kitty | alive animal mammal pet legs4 meat noise house soft ~outside
a horse | horse, pony | alive animal mammal legs4 farm big outside noise
a cow | cow, cows, cattle | alive animal mammal legs4 farm big outside noise
a pig | pig, piggy, hog | alive animal mammal legs4 farm outside noise
a sheep | sheep, lamb | alive animal mammal legs4 farm outside soft noise
a chicken | chicken, hen, rooster | alive animal bird eggs farm outside noise ~fly ~food
a duck | duck | alive animal bird eggs fly water outside nature noise ~farm
an eagle | eagle | alive animal bird eggs fly meat outside nature ~danger
a penguin | penguin | alive animal bird eggs water meat outside nature
an owl | owl | alive animal bird eggs fly meat outside nature noise
a parrot | parrot | alive animal bird eggs fly pet noise ~house
a shark | shark | alive animal water meat danger big nature outside
a goldfish | goldfish | alive animal water pet hand house
a whale | whale | alive animal mammal water big nature outside noise
a dolphin | dolphin | alive animal mammal water big nature outside meat noise
an octopus | octopus | alive animal water meat nature outside
a crab | crab | alive animal water meat nature outside eggs ~food
a lion | lion | alive animal mammal legs4 meat danger big nature outside noise
a tiger | tiger | alive animal mammal legs4 meat danger big nature outside noise
an elephant | elephant | alive animal mammal legs4 big nature outside noise
a giraffe | giraffe | alive animal mammal legs4 big nature outside
a monkey | monkey | alive animal mammal nature outside noise ~legs4
a bear | bear | alive animal mammal legs4 meat danger big nature outside noise
a wolf | wolf | alive animal mammal legs4 meat danger nature outside noise
a rabbit | rabbit, bunny | alive animal mammal legs4 pet soft outside nature ~farm ~house
a mouse | mouse, mice | alive animal mammal legs4 hand nature ~house ~pet
a hamster | hamster | alive animal mammal legs4 pet hand soft house
a snake | snake | alive animal eggs meat danger nature outside ~pet
a frog | frog | alive animal water eggs nature outside hand noise
a turtle | turtle, tortoise | alive animal legs4 water eggs nature outside ~pet
a spider | spider | alive animal bug eggs meat hand nature ~house ~danger
a bee | bee, bumblebee, honeybee | alive animal bug fly eggs hand nature outside noise ~danger
a butterfly | butterfly | alive animal bug fly eggs hand nature outside
an ant | ant, ants | alive animal bug eggs hand nature outside ~house
a mosquito | mosquito | alive animal bug fly eggs hand nature outside noise ~danger
a dinosaur | dinosaur, t rex, trex | animal big meat danger eggs nature famous ~movie
a dragon | dragon | madeup fly big danger eggs meat movie famous ~animal
a unicorn | unicorn | madeup legs4 movie ~animal ~famous
a pizza | pizza | food hotfood ~kitchen ~house
a burger | burger, hamburger, cheeseburger | food hotfood ~hand
a hot dog | hot dog, hotdog | food hotfood hand
spaghetti | spaghetti, pasta, noodles | food hotfood kitchen
sushi | sushi | food ~water
a taco | taco, tacos | food hotfood hand
ice cream | ice cream | food sweet ~kitchen ~house ~hand
chocolate | chocolate | food sweet hand
a cookie | cookie, cookies | food sweet hand kitchen
a cake | cake, birthday cake | food sweet kitchen
a donut | donut, doughnut | food sweet hand
popcorn | popcorn | food ~hotfood ~hand ~movie
a sandwich | sandwich | food hand kitchen
french fries | fries, french fries | food hotfood ~hand
an egg | egg | food kitchen hand hotfood ~alive
bread | bread, toast | food kitchen hand ~hotfood
cheese | cheese | food kitchen ~hand ~farm
an apple | apple | food fruitveg plant sweet hand kitchen ~alive ~nature
a banana | banana | food fruitveg plant sweet hand kitchen ~alive
an orange | orange | food fruitveg plant sweet hand kitchen ~alive
a strawberry | strawberry | food fruitveg plant sweet hand ~alive ~nature
a watermelon | watermelon | food fruitveg plant sweet ~alive
a carrot | carrot | food fruitveg plant hand kitchen ~alive
a potato | potato | food fruitveg plant hand kitchen hotfood ~alive
broccoli | broccoli | food fruitveg plant hand kitchen ~alive ~hotfood
a pineapple | pineapple | food fruitveg plant sweet ~alive ~sharp
a lemon | lemon | food fruitveg plant hand kitchen ~alive
coffee | coffee | drink kitchen ~hotfood ~food
milk | milk | drink kitchen ~farm ~food
water | water | drink nature kitchen house outside bathroom
orange juice | juice, orange juice | drink sweet kitchen
soda | soda, coke, pop | drink sweet
tea | tea | drink kitchen ~hotfood
a phone | phone, cell phone, smartphone, iphone, cellphone | electric screen hand house noise ~school
a laptop | laptop, computer | electric screen house school
a TV | tv, television | electric screen house noise ~big
a toaster | toaster | electric kitchen house metal
a microwave | microwave | electric kitchen house metal noise
a fridge | fridge, refrigerator | electric kitchen house big metal ~noise
an oven | oven, stove | electric kitchen house metal ~big
a blender | blender | electric kitchen house noise
a fork | fork | metal kitchen house hand ~sharp ~tool
a spoon | spoon | metal kitchen house hand ~tool
a knife | knife | metal kitchen house hand sharp danger tool
a cup | cup, mug | kitchen house hand
a plate | plate | kitchen house hand
a chair | chair | house school ~wood
a table | table, desk | house school ~wood ~kitchen
a bed | bed | house big soft
a couch | couch, sofa | house big soft
a lamp | lamp | electric house school
a clock | clock | house school noise ~electric ~hand
a pillow | pillow | house soft ~hand
a blanket | blanket | house soft ~wear
a toothbrush | toothbrush | bathroom house hand ~electric
a toilet | toilet | bathroom house ~noise
a mirror | mirror | bathroom house ~hand
soap | soap | bathroom house hand kitchen
a towel | towel | bathroom house soft ~wear
a door | door | house school ~wood
a window | window | house school
a key | key, keys | metal hand house ~tool
scissors | scissors | metal sharp hand house school tool
a hammer | hammer | tool metal hand noise ~house
a pencil | pencil, pen | hand school wood house ~tool
a book | book | hand school house
a backpack | backpack, bag | wear school ~soft
an umbrella | umbrella | hand outside ~wear ~tool
a candle | candle | house hand ~danger
a vacuum | vacuum, vacuum cleaner | electric house noise
a camera | camera | electric hand ~screen
headphones | headphones, earbuds | electric wear hand ~music ~noise
a remote | remote, remote control | electric hand house
a light bulb | light bulb, lightbulb, bulb | electric hand house
a guitar | guitar | music noise wood ~electric
a piano | piano | music noise big house ~wood ~electric
a drum | drum, drums | music noise ~big
a balloon | balloon | hand ~fly ~soft ~noise
a teddy bear | teddy bear, teddy, stuffed animal | soft house hand ~animal ~madeup
a ball | ball, soccer ball, basketball, football, baseball | sport hand outside ~soft
a bicycle | bicycle, bike | vehicle wheels outside metal ~sport
a skateboard | skateboard | wheels outside sport wood ~vehicle
shoes | shoe, shoes, sneakers | wear house outside ~soft
a hat | hat, cap | wear hand ~soft
a shirt | shirt, t shirt, tshirt | wear soft house
glasses | glasses, sunglasses | wear hand
socks | sock, socks | wear soft hand house
a ring | ring | wear metal hand
money | money, dollar, cash | hand ~house
a sword | sword | metal sharp danger ~tool ~movie
a rock | rock, stone | nature outside ~hand
a tree | tree | alive plant nature outside big wood
a flower | flower, rose | alive plant nature outside hand ~house
grass | grass | alive plant nature outside
a cactus | cactus | alive plant nature outside sharp ~house
the sun | sun | nature outside big ~danger
the moon | moon | nature outside big ~famous
a cloud | cloud | nature outside big ~soft ~fly
snow | snow | nature outside ~soft
fire | fire | danger nature ~outside ~house
a rainbow | rainbow | nature outside big
a star | star, stars | nature outside big
a car | car | vehicle wheels metal outside big noise ~electric
a bus | bus | vehicle wheels metal outside big noise ~school
a train | train | vehicle wheels metal outside big noise ~electric
a plane | plane, airplane, jet | vehicle fly metal outside big noise ~wheels
a helicopter | helicopter | vehicle fly metal outside big noise
a boat | boat, ship | vehicle outside big ~water ~wood ~metal
a rocket | rocket, spaceship | vehicle fly metal big noise danger
a motorcycle | motorcycle, motorbike | vehicle wheels metal outside noise danger
a truck | truck | vehicle wheels metal outside big noise
a submarine | submarine | vehicle water metal big
a tractor | tractor | vehicle wheels farm metal outside big noise
a beach | beach | place outside nature ~water
a school | school | place big school
a hospital | hospital | place big
the zoo | zoo | place outside big
a library | library | place big ~school
a park | park | place outside nature
a mall | mall | place big
a restaurant | restaurant | place kitchen
Paris | paris | place city famous big
New York | new york, nyc | place city famous big
Disneyland | disneyland, disney world | place famous ~movie
an airport | airport | place big noise
a farm | farm | place farm outside
a desert | desert | place nature outside big
the ocean | ocean, sea | place nature water big outside
a volcano | volcano | place nature outside big danger
the Eiffel Tower | eiffel tower | place famous big metal outside ~city
Mickey Mouse | mickey mouse, mickey | person madeup movie famous ~animal
Spider-Man | spider man, spiderman | person madeup movie famous
Batman | batman, bat man | person madeup movie famous
Santa Claus | santa, santa claus | person madeup famous
Harry Potter | harry potter | person madeup movie famous
Pikachu | pikachu | madeup movie famous ~animal ~electric
Mario | mario, super mario | person madeup famous movie
a teacher | teacher | person alive school ~mammal
a doctor | doctor | person alive ~mammal
a baby | baby | person alive house noise ~soft ~mammal
Taylor Swift | taylor swift | person alive famous ~music ~mammal
a robot | robot | electric metal noise ~movie ~madeup ~person
"""


def _parse(raw: str) -> tuple[Thing, ...]:
    things = []
    for line in raw.strip().splitlines():
        name, aliases, traits = (part.strip() for part in line.split("|"))
        tags = traits.split()
        unknown = {t.lstrip("~") for t in tags} - TRAIT.keys()
        if unknown:
            raise ValueError(f"{name}: no trait {sorted(unknown)}")
        things.append(Thing(
            name=name,
            aliases=tuple(a.strip().lower() for a in aliases.split(",") if a.strip()),
            yes=frozenset(t for t in tags if not t.startswith("~")),
            sort=frozenset(t[1:] for t in tags if t.startswith("~")),
        ))
    return tuple(things)


THINGS: tuple[Thing, ...] = _parse(_RAW)
