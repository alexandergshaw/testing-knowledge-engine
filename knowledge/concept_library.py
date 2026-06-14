"""Curated, layman-friendly lecture content — hand-written so the lecture deck
reads like the reference (Gemini) deck without any LLM. Programming concepts get
plain-English explanations + a clean canonical code example; intro-CS topics get
explanations only. Anything not covered here falls back to (cleaned) retrieval.

Keys for programming concepts match the canonical names produced by
`knowledge.lecture.extract_concepts`; intro-CS topics are matched from objective
text via `match_topic`.
"""

LIBRARY = {
    # --- programming concepts (explanation + code) -------------------------
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
            "lines": ["is_adult = age >= 18", "if is_adult:", '    print("Access granted")'],
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
}

# Conceptual intro-CS topics, matched by phrases in the objective text.
TOPIC_MATCHERS = {
    "Computer Science in the Real World": [
        "real world", "real-world", "computer science in", "examples of computer science",
        "applications of computer",
    ],
    "Problem-Solving Strategies": ["problem-solving", "problem solving"],
    "Algorithms": ["algorithm"],
    "Debugging": ["debug"],
    "Pseudocode": ["pseudocode"],
}


def explanation_for(name):
    """Curated layman explanation bullets for a concept/topic name, or None."""
    entry = LIBRARY.get(name)
    return list(entry["explanation"]) if entry else None


def code_for(name, language=""):
    """A curated code example for a concept, or None. Returns
    {caption, lines, language}; prefers the requested language, then Python."""
    entry = LIBRARY.get(name)
    if not entry or "code" not in entry:
        return None
    examples = entry["code"]
    if language in examples:
        chosen = language
    elif "Python" in examples:
        chosen = "Python"
    else:
        chosen = next(iter(examples))
    example = examples[chosen]
    return {"caption": example["caption"], "lines": list(example["lines"]), "language": chosen}


def match_topic(text):
    """Conceptual intro-CS topic name from objective text, or None."""
    lowered = text.lower()
    for name, phrases in TOPIC_MATCHERS.items():
        if any(phrase in lowered for phrase in phrases):
            return name
    return None
