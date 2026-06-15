"""Curated, layman-friendly lecture content — hand-written so the lecture deck
reads like the reference (Gemini) deck without any LLM. Programming concepts get
plain-English explanations plus a full worked-example *unit* (a canonical code
example, a line-by-line walkthrough, a practice challenge, and a distinct
solution); intro-CS topics get explanations only. Anything not covered here
falls back to (cleaned) retrieval.

Keys for programming concepts match the canonical names produced by
`knowledge.lecture.extract_concepts`; intro-CS topics are matched from objective
text via `match_topic`.

Each language entry under "code" is self-contained:
  {caption, lines, walkthrough, practice, answer:{caption, lines}}
`code_for` reads caption/lines (back-compat); `unit_for` reads the whole unit.
The practice slide deliberately carries NO solution — the unit builder shows the
example's own code there as a read-only reference, and only the answer carries a
distinct, runnable solution.
"""

LIBRARY = {
    # --- programming concepts (explanation + worked-example unit) -----------
    "Variables": {
        "explanation": [
            "A variable is a labeled box that stores a value you can reuse.",
            "You create one by giving it a name and assigning a value with '='.",
            "The name lets you use the value without retyping it.",
            "Variables can hold numbers, text, true/false values, and more.",
        ],
        "code": {"Python": {
            "caption": "Storing and reusing values in variables.",
            "lines": ['city = "Denver"', "temperature = 72", "is_raining = False", "print(city, temperature)"],
            "walkthrough": [
                'city stores the text "Denver" — a string value.',
                "temperature stores the whole number 72 — an integer.",
                "is_raining stores False — a boolean (true/false) value.",
                "print shows the city and temperature on screen.",
            ],
            "practice": [
                "Create a variable 'username' holding your name as text.",
                "Create a variable 'age' holding a whole number, then print both.",
            ],
            "answer": {
                "caption": "Storing a name and age, then printing them.",
                "lines": ['username = "Ada"', "age = 30", "print(username, age)"],
            },
        }},
    },
    "Data Types": {
        "explanation": [
            "A data type tells the computer what kind of value something is.",
            "Integers (int) are whole numbers, like items in a shopping cart.",
            "Floats (float) are decimals, used for precise values like price.",
            "Strings (str) are text, and booleans (bool) are simply True or False.",
            "Using the right type keeps math correct and prevents errors.",
        ],
        "code": {"Python": {
            "caption": "Defining variables with different numeric types.",
            "lines": ["items_count = 5        # int", "price = 19.99          # float",
                      "total = items_count * price", "print(total)"],
            "walkthrough": [
                "items_count is an integer — a whole number of items.",
                "price is a float — a decimal value for currency.",
                "total multiplies the two, mixing an int and a float.",
                "print shows the resulting total.",
            ],
            "practice": [
                "Create an integer 'score' and a float 'percentage'.",
                "Print both values to confirm they are stored.",
            ],
            "answer": {
                "caption": "Defining an integer score and a float percentage.",
                "lines": ["score = 95", "percentage = 95.5", "print(score, percentage)"],
            },
        }},
    },
    "Loops": {
        "explanation": [
            "A loop repeats a block of code so you don't rewrite it.",
            "A 'for' loop runs once for each item in a collection.",
            "A 'while' loop keeps going until a condition becomes false.",
            "Loops let programs handle long lists automatically.",
        ],
        "code": {"Python": {
            "caption": "Looping over a list of values.",
            "lines": ["scores = [85, 92, 78]", "for score in scores:", "    print(score)"],
            "walkthrough": [
                "scores is a list holding three numbers.",
                "The for loop takes each score in turn.",
                "print runs once per item, showing every score.",
            ],
            "practice": [
                "Make a list of three names.",
                "Use a for loop to print each name on its own line.",
            ],
            "answer": {
                "caption": "Looping over a list of names.",
                "lines": ['names = ["Ada", "Alan", "Grace"]', "for name in names:", "    print(name)"],
            },
        }},
    },
    "Conditionals": {
        "explanation": [
            "Conditionals let a program make decisions.",
            "An 'if' statement runs code only when a condition is true.",
            "'else' provides a fallback when the condition is false.",
            "It's like grabbing an umbrella only if it's raining.",
        ],
        "code": {"Python": {
            "caption": "Making a decision with if/else.",
            "lines": ["score = 85", "if score >= 90:", '    print("Excellent")',
                      "else:", '    print("Keep practicing")'],
            "walkthrough": [
                "score holds the value to be checked.",
                "The if statement tests whether score is at least 90.",
                'When true, it prints "Excellent".',
                'Otherwise the else branch prints "Keep practicing".',
            ],
            "practice": [
                "Set a variable 'temperature'.",
                'Print "Hot" if it is above 30, otherwise print "Mild".',
            ],
            "answer": {
                "caption": "Choosing a message based on temperature.",
                "lines": ["temperature = 35", "if temperature > 30:", '    print("Hot")',
                          "else:", '    print("Mild")'],
            },
        }},
    },
    "Control Structures": {
        "explanation": [
            "Control structures decide the order in which code runs.",
            "Conditionals (if/else) let programs make decisions based on inputs.",
            "Loops (for/while) automate repetitive tasks.",
            "Together they turn a fixed list of steps into flexible behavior.",
        ],
        "code": {"Python": {
            "caption": "Using an if-statement inside a loop to filter data.",
            "lines": ["scores = [85, 92, 78, 95]", "for score in scores:",
                      "    if score >= 90:", '        print("Excellent!")'],
            "walkthrough": [
                "scores is a list of four test results.",
                "The for loop visits each score in order.",
                "Inside the loop, if checks whether the score is at least 90.",
                'Only scores that pass the test print "Excellent!".',
            ],
            "practice": [
                "Loop over a list of numbers.",
                "Print only the numbers that are even.",
            ],
            "answer": {
                "caption": "Printing only the even numbers in a list.",
                "lines": ["numbers = [1, 2, 3, 4, 5, 6]", "for number in numbers:",
                          "    if number % 2 == 0:", "        print(number)"],
            },
        }},
    },
    "Functions": {
        "explanation": [
            "Functions act like reusable recipes for repeating tasks.",
            "You define the steps once, then call the function when needed.",
            "They group related logic so code is easier to read.",
            "Inputs (parameters) let the same function work on different data.",
        ],
        "code": {"Python": {
            "caption": "Creating a function to calculate a discount.",
            "lines": ["def apply_discount(price, rate):", "    return price * (1 - rate)", "",
                      "final_price = apply_discount(100, 0.2)"],
            "walkthrough": [
                "def names a new function and lists its inputs.",
                "price and rate are parameters the caller provides.",
                "return sends back the discounted price.",
                "The last line calls the function with real values.",
            ],
            "practice": [
                "Write a function 'area' that takes width and height.",
                "Return their product, then call it with two numbers.",
            ],
            "answer": {
                "caption": "A function that returns the area of a rectangle.",
                "lines": ["def area(width, height):", "    return width * height", "",
                          "print(area(4, 5))"],
            },
        }},
    },
    "Lists & Arrays": {
        "explanation": [
            "A list stores many values in a single, ordered container.",
            "Each item has a position (index) starting at 0.",
            "You can add, remove, or change items as the program runs.",
            "Lists are perfect for collections like scores or names.",
        ],
        "code": {"Python": {
            "caption": "Building and reading a list.",
            "lines": ['names = ["Ada", "Alan", "Grace"]', 'names.append("Linus")', "print(names[0])"],
            "walkthrough": [
                "names is a list holding three strings.",
                'append adds "Linus" to the end of the list.',
                "names[0] reads the first item, since indexes start at 0.",
            ],
            "practice": [
                "Create a list of three numbers.",
                "Append a fourth number, then print the last item.",
            ],
            "answer": {
                "caption": "Adding to a list and reading the last item.",
                "lines": ["numbers = [10, 20, 30]", "numbers.append(40)", "print(numbers[-1])"],
            },
        }},
    },
    "Dictionaries": {
        "explanation": [
            "A dictionary stores values by a label (key), not a position.",
            "It's like a real dictionary: look up a word to get its definition.",
            "Each entry is a key paired with a value.",
            "Great for records like a user's name, age, and email.",
        ],
        "code": {"Python": {
            "caption": "Storing and looking up values by key.",
            "lines": ['user = {"name": "Ada", "age": 36}', 'print(user["name"])',
                      'user["email"] = "ada@example.com"'],
            "walkthrough": [
                "user is a dictionary with two key/value pairs.",
                'user["name"] looks up the value stored under "name".',
                'The last line adds a new "email" entry.',
            ],
            "practice": [
                "Create a dictionary for a book with 'title' and 'author'.",
                "Print the title, then add a 'year' entry.",
            ],
            "answer": {
                "caption": "Reading and adding dictionary entries.",
                "lines": ['book = {"title": "Dune", "author": "Herbert"}', 'print(book["title"])',
                          'book["year"] = 1965'],
            },
        }},
    },
    "Classes & Objects": {
        "explanation": [
            "A class is a blueprint for creating objects.",
            "An object bundles related data and the actions on it.",
            "It's like a cookie cutter (class) and the cookies (objects).",
            "Each object has its own values but shares the same behavior.",
        ],
        "code": {"Python": {
            "caption": "Defining a class and creating an object.",
            "lines": ["class Dog:", "    def __init__(self, name):", "        self.name = name", "",
                      'rex = Dog("Rex")', "print(rex.name)"],
            "walkthrough": [
                "class Dog defines a blueprint for dog objects.",
                "__init__ runs automatically when a new Dog is created.",
                "self.name stores the name on the object.",
                'Dog("Rex") makes an object; rex.name reads its name.',
            ],
            "practice": [
                "Define a class 'Car' that stores a 'brand'.",
                "Create one car and print its brand.",
            ],
            "answer": {
                "caption": "A simple class with one stored value.",
                "lines": ["class Car:", "    def __init__(self, brand):", "        self.brand = brand", "",
                          'my_car = Car("Toyota")', "print(my_car.brand)"],
            },
        }},
    },
    "Strings": {
        "explanation": [
            "A string is text — letters, numbers, and symbols in quotes.",
            "You can join strings together to build messages.",
            "Strings have handy actions like uppercase and length.",
            "They're used everywhere: names, messages, and labels.",
        ],
        "code": {"Python": {
            "caption": "Combining and transforming text.",
            "lines": ['name = "ada"', 'greeting = "Hello, " + name.title()', "print(greeting)"],
            "walkthrough": [
                'name holds the text "ada".',
                "title() capitalizes it, and + joins the two strings.",
                "print shows the finished greeting.",
            ],
            "practice": [
                "Store a word in lowercase.",
                "Print it in uppercase using .upper().",
            ],
            "answer": {
                "caption": "Converting text to uppercase.",
                "lines": ['word = "python"', "print(word.upper())"],
            },
        }},
    },
    "Recursion": {
        "explanation": [
            "Recursion is when a function calls itself to solve a smaller piece.",
            "Each call works on a simpler version of the problem.",
            "A base case stops the calls so it doesn't run forever.",
            "It's like nesting dolls — open one to find a smaller one.",
        ],
        "code": {"Python": {
            "caption": "Counting down with a recursive function.",
            "lines": ["def countdown(n):", "    if n == 0:", "        return", "    print(n)",
                      "    countdown(n - 1)"],
            "walkthrough": [
                "countdown calls itself with a smaller number each time.",
                "The if n == 0 base case stops the recursion.",
                "print shows the current value.",
                "countdown(n - 1) repeats with the next-lower number.",
            ],
            "practice": [
                "Write a recursive function 'total' that sums 1..n.",
                "Use a base case of n == 0 returning 0.",
            ],
            "answer": {
                "caption": "Summing 1..n with recursion.",
                "lines": ["def total(n):", "    if n == 0:", "        return 0",
                          "    return n + total(n - 1)"],
            },
        }},
    },
    "Exceptions & Errors": {
        "explanation": [
            "An exception is the program's way of reporting a problem.",
            "Unhandled, an error stops the program completely.",
            "'try' runs risky code; 'except' catches the problem.",
            "This lets the program recover instead of crashing.",
        ],
        "code": {"Python": {
            "caption": "Handling an error gracefully.",
            "lines": ["try:", "    result = 10 / 0", "except ZeroDivisionError:",
                      '    print("Can\'t divide by zero")'],
            "walkthrough": [
                "try wraps code that might fail.",
                "10 / 0 raises a ZeroDivisionError.",
                "except catches that specific error.",
                "The program prints a message instead of crashing.",
            ],
            "practice": [
                'Try converting the text "abc" to an int.',
                "Catch the ValueError and print a friendly message.",
            ],
            "answer": {
                "caption": "Catching a bad conversion.",
                "lines": ["try:", '    number = int("abc")', "except ValueError:",
                          '    print("Not a valid number")'],
            },
        }},
    },
    "Booleans": {
        "explanation": [
            "A boolean is a value that is either True or False.",
            "They answer yes/no questions inside a program.",
            "Comparisons like 5 > 3 produce booleans.",
            "They drive decisions in if-statements and loops.",
        ],
        "code": {"Python": {
            "caption": "Using a boolean to make a decision.",
            "lines": ["age = 20", "is_adult = age >= 18", "if is_adult:", '    print("Access granted")'],
            "walkthrough": [
                "age holds the value to test.",
                "age >= 18 compares two numbers and yields True or False.",
                "is_adult stores that boolean result.",
                "The if runs its block only when is_adult is True.",
            ],
            "practice": [
                "Create a boolean 'has_ticket'.",
                'Print "Welcome" only when it is True.',
            ],
            "answer": {
                "caption": "Acting on a boolean value.",
                "lines": ["has_ticket = True", "if has_ticket:", '    print("Welcome")'],
            },
        }},
    },
    "Operators": {
        "explanation": [
            "Operators are symbols that perform actions on values.",
            "Math operators (+, -, *, /) do arithmetic.",
            "Comparison operators (>, <, ==) ask true/false questions.",
            "Logical operators (and, or, not) combine conditions.",
        ],
        "code": {"Python": {
            "caption": "Combining math and comparison operators.",
            "lines": ["total = 5 * 20", "is_expensive = total > 50", "print(total, is_expensive)"],
            "walkthrough": [
                "* multiplies 5 by 20 to make total.",
                "> compares total to 50, giving a boolean.",
                "print shows both the number and the comparison result.",
            ],
            "practice": [
                "Add two numbers into 'total'.",
                "Use 'and' to check total is over 10 and even.",
            ],
            "answer": {
                "caption": "Combining arithmetic and logical operators.",
                "lines": ["total = 8 + 6", "is_big_even = total > 10 and total % 2 == 0",
                          "print(total, is_big_even)"],
            },
        }},
    },
    "File I/O": {
        "explanation": [
            "File I/O lets a program read from and write to files.",
            "Writing saves results so they last after the program ends.",
            "Reading pulls saved data back into the program.",
            "Using 'with' closes the file for you so data isn't lost.",
        ],
        "code": {"Python": {
            "caption": "Writing text to a file and reading it back.",
            "lines": ['with open("note.txt", "w") as f:', '    f.write("Hello")', "",
                      'with open("note.txt") as f:', "    print(f.read())"],
            "walkthrough": [
                'open(..., "w") opens the file for writing.',
                'f.write saves the text "Hello".',
                "Opening again in read mode reads it back.",
                "with closes the file automatically each time.",
            ],
            "practice": [
                'Write the line "Done" to a file called log.txt.',
                "Read the file back and print its contents.",
            ],
            "answer": {
                "caption": "Writing a line and reading it back.",
                "lines": ['with open("log.txt", "w") as f:', '    f.write("Done")', "",
                          'with open("log.txt") as f:', "    print(f.read())"],
            },
        }},
    },
    "Algorithms": {
        "explanation": [
            "An algorithm is a precise, step-by-step recipe to solve a problem.",
            "Good algorithms are correct and finish in a reasonable time.",
            "The same problem can be solved by faster or slower algorithms.",
            "They power everything from sorting lists to routing maps.",
        ],
        "code": {"Python": {
            "caption": "Sorting a list of numbers.",
            "lines": ["numbers = [5, 2, 9, 1]", "numbers.sort()", "print(numbers)"],
            "walkthrough": [
                "numbers is an unsorted list.",
                "sort() rearranges it in ascending order.",
                "print shows the sorted result.",
            ],
            "practice": [
                "Make a list of numbers.",
                "Sort it in descending order and print it.",
            ],
            "answer": {
                "caption": "Sorting a list from high to low.",
                "lines": ["numbers = [3, 8, 1, 6]", "numbers.sort(reverse=True)", "print(numbers)"],
            },
        }},
    },
    # --- intro-CS topics (explanation only) --------------------------------
    "Computer Science in the Real World": {
        "explanation": [
            "Streaming services use algorithms to recommend your next show.",
            "GPS apps find the fastest route through traffic in real time.",
            "Search engines rank billions of pages in a fraction of a second.",
            "Banks use code to detect fraud and keep money safe.",
            "Almost every modern convenience is powered by computer science.",
        ],
    },
    "Problem-Solving Strategies": {
        "explanation": [
            "Decomposition: break a big problem into small, manageable tasks.",
            "Pattern recognition: spot similarities to problems you've solved.",
            "Abstraction: focus on what matters and ignore the rest.",
            "Algorithm design: write clear, step-by-step instructions.",
            "Test and refine: try your solution, then improve it.",
        ],
    },
    "Debugging": {
        "explanation": [
            "Debugging is finding and fixing mistakes in your code.",
            "Read the error message — it often points to the line and cause.",
            "Print values to see what the program is actually doing.",
            "Fix one problem at a time and re-test.",
        ],
    },
    "Pseudocode": {
        "explanation": [
            "Pseudocode is a plain-language sketch of a program's logic.",
            "It ignores exact syntax so you can focus on the steps.",
            "It's a bridge between an idea and real code.",
            "Write it first, then translate it into a language.",
        ],
    },
    # --- non-CS concepts (explanation + a curated illustration) -------------
    # High-traffic topics across other fields, so a conceptual lecture reads
    # like an instructor-made deck offline. Retrieval still covers the long tail.
    "Classical Conditioning": {
        "explanation": [
            "Classical conditioning is learning to link two things that occur together.",
            "A neutral cue paired with a meaningful one starts to trigger the same response.",
            "Ivan Pavlov rang a bell before feeding dogs until the bell alone made them salivate.",
            "It explains many automatic emotional and physical reactions.",
        ],
        "illustration": "For example, if a song always played during happy childhood meals, hearing it later can make you feel hungry or nostalgic.",
    },
    "Operant Conditioning": {
        "explanation": [
            "Operant conditioning is learning from the consequences of our actions.",
            "Rewards make a behavior more likely; punishments make it less likely.",
            "B.F. Skinner showed rats pressing a lever more often when it released food.",
            "It underlies habits, training, and much of everyday motivation.",
        ],
        "illustration": "For example, a student praised for raising their hand starts to participate more often.",
    },
    "Cognitive Dissonance": {
        "explanation": [
            "Cognitive dissonance is the discomfort of holding two conflicting beliefs.",
            "To ease it, people often change a belief or justify their behavior.",
            "Leon Festinger described it after studying a group whose prophecy failed.",
            "It explains why we rationalize choices that don't match our values.",
        ],
        "illustration": "For example, a smoker who knows smoking is harmful may downplay the risk to stay comfortable continuing.",
    },
    "Maslow's Hierarchy of Needs": {
        "explanation": [
            "Maslow's hierarchy ranks human needs from basic to higher-level.",
            "Physiological and safety needs come first, then love, esteem, and self-actualization.",
            "People generally meet lower needs before pursuing higher ones.",
            "It's a common framework for motivation in psychology and business.",
        ],
        "illustration": "For example, someone worried about food and rent rarely focuses on creative self-fulfillment until those basics are secure.",
    },
    "The Bystander Effect": {
        "explanation": [
            "The bystander effect is the tendency to help less when others are present.",
            "Responsibility feels diffused — each person assumes someone else will act.",
            "It drew research attention after the 1964 Kitty Genovese case.",
            "Naming a specific person to help often breaks the effect.",
        ],
        "illustration": "For example, in a crowded station people may walk past someone who has collapsed, each assuming another will step in.",
    },
    "Photosynthesis": {
        "explanation": [
            "Photosynthesis is how plants make their own food from sunlight.",
            "Leaves use light, water, and carbon dioxide to produce sugar.",
            "Oxygen is released as a by-product, which animals breathe.",
            "It's the foundation of most food chains on Earth.",
        ],
        "illustration": "For example, a tree turns sunlight and air into the sugars it uses to grow new leaves and wood.",
    },
    "Natural Selection": {
        "explanation": [
            "Natural selection is how species change over generations.",
            "Individuals with helpful traits survive and reproduce more.",
            "Those traits become more common in the population over time.",
            "Charles Darwin proposed it as the engine of evolution.",
        ],
        "illustration": "For example, moths with darker wings survived better in soot-darkened cities, so dark moths became more common.",
    },
    "Cells": {
        "explanation": [
            "The cell is the basic building block of all living things.",
            "Some organisms are a single cell; others have trillions.",
            "Cells carry out life processes like using energy and reproducing.",
            "Plant and animal cells share parts but differ in some structures.",
        ],
        "illustration": "For example, your skin constantly makes new cells to replace ones that wear away.",
    },
    "DNA": {
        "explanation": [
            "DNA is the molecule that stores an organism's genetic instructions.",
            "It is shaped like a twisted ladder called a double helix.",
            "Its sequence acts as a code for building proteins.",
            "DNA is passed from parents to offspring.",
        ],
        "illustration": "For example, DNA inherited from your parents helps determine traits like eye color.",
    },
    "Supply and Demand": {
        "explanation": [
            "Supply and demand describe how prices form in a market.",
            "Demand is how much buyers want at each price; supply is how much sellers offer.",
            "Price tends to settle where the two meet — the equilibrium.",
            "Shortages push prices up; surpluses push them down.",
        ],
        "illustration": "For example, when a popular toy sells out before the holidays, sellers raise the price until demand cools.",
    },
    "Opportunity Cost": {
        "explanation": [
            "Opportunity cost is the value of the next-best option you give up.",
            "Every choice means forgoing something else.",
            "It applies to money, time, and resources alike.",
            "Good decisions weigh what's gained against what's sacrificed.",
        ],
        "illustration": "For example, spending Saturday studying has the opportunity cost of the shift you could have worked for pay.",
    },
    "Inflation": {
        "explanation": [
            "Inflation is a general rise in prices over time.",
            "As prices climb, each unit of money buys less.",
            "Moderate inflation is normal; rapid inflation erodes savings.",
            "Central banks adjust interest rates to keep it in check.",
        ],
        "illustration": "For example, if a $1 candy bar costs $1.05 a year later, that's roughly 5% inflation.",
    },
    "Newton's Laws of Motion": {
        "explanation": [
            "Newton's three laws describe how objects move under forces.",
            "First: an object keeps its motion unless a force acts on it.",
            "Second: force equals mass times acceleration (F = ma).",
            "Third: every action has an equal and opposite reaction.",
        ],
        "illustration": "For example, a rocket pushes gas downward and the gas pushes the rocket upward — Newton's third law.",
    },
    "Gravity": {
        "explanation": [
            "Gravity is the force that pulls objects with mass toward each other.",
            "It gives objects weight and keeps planets in orbit.",
            "On Earth it pulls everything downward at about 9.8 m/s².",
            "The more massive an object, the stronger its gravitational pull.",
        ],
        "illustration": "For example, gravity makes a dropped ball fall and holds the Moon in orbit around Earth.",
    },
    "Atoms": {
        "explanation": [
            "An atom is the smallest unit of a chemical element.",
            "It has a nucleus of protons and neutrons, with electrons around it.",
            "The number of protons defines which element it is.",
            "Atoms combine to form molecules and everything around us.",
        ],
        "illustration": "For example, a single drop of water contains billions of atoms of hydrogen and oxygen.",
    },
    "The Periodic Table": {
        "explanation": [
            "The periodic table organizes all known chemical elements.",
            "Elements are ordered by their number of protons.",
            "Columns group elements with similar properties.",
            "It lets chemists predict how elements behave and react.",
        ],
        "illustration": "For example, the elements in the far-right column — like helium and neon — are all stable, unreactive gases.",
    },
}

# Conceptual topics, matched by phrases in the objective text. More specific
# phrases should precede broader ones (first match wins).
TOPIC_MATCHERS = {
    "Computer Science in the Real World": [
        "real world", "real-world", "computer science in", "examples of computer science",
        "applications of computer",
    ],
    "Problem-Solving Strategies": ["problem-solving", "problem solving"],
    "Algorithms": ["algorithm"],
    "Debugging": ["debug"],
    "Pseudocode": ["pseudocode"],
    # non-CS fields
    "Classical Conditioning": ["classical conditioning", "pavlov"],
    "Operant Conditioning": ["operant conditioning", "reinforcement", "skinner"],
    "Cognitive Dissonance": ["cognitive dissonance"],
    "Maslow's Hierarchy of Needs": ["maslow", "hierarchy of needs"],
    "The Bystander Effect": ["bystander"],
    "Photosynthesis": ["photosynthesis"],
    "Natural Selection": ["natural selection", "survival of the fittest"],
    "Cells": ["cell biology", "cell structure", "cell theory"],
    "DNA": ["dna", "double helix", "genetic code"],
    "Supply and Demand": ["supply and demand"],
    "Opportunity Cost": ["opportunity cost"],
    "Inflation": ["inflation"],
    "Newton's Laws of Motion": ["newton's laws", "newtons laws", "laws of motion"],
    "Gravity": ["gravity", "gravitation"],
    "Atoms": ["atomic structure", "atoms", "the atom"],
    "The Periodic Table": ["periodic table"],
}


def explanation_for(name):
    """Curated layman explanation bullets for a concept/topic name, or None."""
    entry = LIBRARY.get(name)
    return list(entry["explanation"]) if entry else None


def illustration_for(name):
    """A curated real-world illustration sentence for a concept, or None."""
    entry = LIBRARY.get(name)
    return entry.get("illustration") if entry else None


def _choose_language(examples, language):
    """The example language to use: the requested one, then Python, then any."""
    if language in examples:
        return language
    if "Python" in examples:
        return "Python"
    return next(iter(examples))


def code_for(name, language=""):
    """A curated code example for a concept, or None. Returns
    {caption, lines, language}; prefers the requested language, then Python."""
    entry = LIBRARY.get(name)
    if not entry or "code" not in entry:
        return None
    examples = entry["code"]
    chosen = _choose_language(examples, language)
    example = examples[chosen]
    return {"caption": example["caption"], "lines": list(example["lines"]), "language": chosen}


def unit_for(name, language=""):
    """The full curated worked-example unit for a concept, or None when the
    concept has no curated code or is missing any unit part. Returns
    {language, example:{caption, lines}, walkthrough, practice,
    answer:{caption, lines}}. The example's code is the single reference snippet
    the walkthrough and practice slides reuse; the answer carries its own code."""
    entry = LIBRARY.get(name)
    if not entry or "code" not in entry:
        return None
    examples = entry["code"]
    chosen = _choose_language(examples, language)
    example = examples[chosen]
    if not all(key in example for key in ("walkthrough", "practice", "answer")):
        return None
    return {
        "language": chosen,
        "example": {"caption": example["caption"], "lines": list(example["lines"])},
        "walkthrough": list(example["walkthrough"]),
        "practice": list(example["practice"]),
        "answer": {
            "caption": example["answer"]["caption"],
            "lines": list(example["answer"]["lines"]),
        },
    }


def match_topic(text):
    """Conceptual intro-CS topic name from objective text, or None."""
    lowered = text.lower()
    for name, phrases in TOPIC_MATCHERS.items():
        if any(phrase in lowered for phrase in phrases):
            return name
    return None
