"""Curated, worked-problem units for quantitative subjects (math, physics,
chemistry, statistics) — hand-written so a quantitative lecture gets a real
worked example, a practice problem, and a distinct solution with no LLM.

Every worked example and answer here is checked by hand for correctness (factual
integrity matters as much as in the case studies). An objective that matches no
entry falls back to the conceptual profile (illustration + review questions), so
coverage gaps degrade gracefully rather than fabricating math.

Each entry:
  explanation:    layman bullets for the concept slide
  worked_example: {problem, steps}   a solved teaching example
  practice:       {problem}          a problem to attempt (no solution shown)
  answer:         {steps}            the distinct solution to the practice problem
"""

LIBRARY = {
    "Order of Operations": {
        "explanation": [
            "Order of operations is the agreed sequence for evaluating an expression.",
            "PEMDAS: Parentheses, Exponents, Multiplication/Division, then Addition/Subtraction.",
            "Multiplication and division are done left to right, as are addition and subtraction.",
            "Following it ensures everyone gets the same answer.",
        ],
        "worked_example": {
            "problem": "Evaluate 3 + 4 × 2² − 6 ÷ 3.",
            "steps": [
                "Exponent first: 2² = 4.",
                "Multiply and divide, left to right: 4 × 4 = 16 and 6 ÷ 3 = 2.",
                "The expression is now 3 + 16 − 2.",
                "Add and subtract, left to right: 3 + 16 = 19, then 19 − 2 = 17.",
                "Result: 17.",
            ],
        },
        "practice": {"problem": "Evaluate 5 + 2 × 3² − 8 ÷ 4."},
        "answer": {
            "steps": [
                "Exponent: 3² = 9.",
                "Multiply and divide: 2 × 9 = 18 and 8 ÷ 4 = 2.",
                "Now 5 + 18 − 2.",
                "Result: 21.",
            ]
        },
    },
    "Percentages": {
        "explanation": [
            "A percentage is a fraction out of 100.",
            "To take a percent of a number, convert it to a decimal and multiply.",
            "For example, 25% becomes 0.25.",
            "Percentages let us compare parts of different-sized wholes.",
        ],
        "worked_example": {
            "problem": "What is 15% of 80?",
            "steps": [
                "Convert 15% to a decimal: 0.15.",
                "Multiply by the whole: 0.15 × 80.",
                "Result: 12.",
            ],
        },
        "practice": {"problem": "What is 20% of 150?"},
        "answer": {"steps": ["Convert 20% to 0.20.", "0.20 × 150 = 30.", "Result: 30."]},
    },
    "Linear Equations": {
        "explanation": [
            "A linear equation sets two expressions equal, with the variable to the first power.",
            "Solve it by isolating the variable on one side.",
            "Do the same operation to both sides to keep the equation balanced.",
            "Undo addition/subtraction first, then multiplication/division.",
        ],
        "worked_example": {
            "problem": "Solve 3x + 4 = 19.",
            "steps": [
                "Subtract 4 from both sides: 3x = 15.",
                "Divide both sides by 3: x = 5.",
                "Check: 3(5) + 4 = 19. ✓",
            ],
        },
        "practice": {"problem": "Solve 5x − 7 = 18."},
        "answer": {"steps": ["Add 7 to both sides: 5x = 25.", "Divide by 5: x = 5.", "Check: 5(5) − 7 = 18. ✓"]},
    },
    "Quadratic Equations": {
        "explanation": [
            "A quadratic equation has the form ax² + bx + c = 0.",
            "Many factor into two binomials that multiply to zero.",
            "If a product is zero, at least one factor must be zero.",
            "That gives up to two solutions for x.",
        ],
        "worked_example": {
            "problem": "Solve x² − 5x + 6 = 0.",
            "steps": [
                "Find two numbers that multiply to 6 and add to −5: −2 and −3.",
                "Factor: (x − 2)(x − 3) = 0.",
                "Set each factor to zero: x − 2 = 0 or x − 3 = 0.",
                "x = 2 or x = 3.",
            ],
        },
        "practice": {"problem": "Solve x² − 7x + 12 = 0."},
        "answer": {
            "steps": [
                "Two numbers multiplying to 12 and adding to −7: −3 and −4.",
                "Factor: (x − 3)(x − 4) = 0.",
                "x = 3 or x = 4.",
            ]
        },
    },
    "Pythagorean Theorem": {
        "explanation": [
            "The Pythagorean theorem relates the sides of a right triangle.",
            "It states a² + b² = c², where c is the hypotenuse.",
            "The hypotenuse is the longest side, opposite the right angle.",
            "It lets you find a missing side when two are known.",
        ],
        "worked_example": {
            "problem": "A right triangle has legs of length 3 and 4. Find the hypotenuse.",
            "steps": [
                "Apply a² + b² = c²: 3² + 4² = c².",
                "9 + 16 = 25, so c² = 25.",
                "Take the square root: c = 5.",
            ],
        },
        "practice": {"problem": "A right triangle has legs of length 6 and 8. Find the hypotenuse."},
        "answer": {"steps": ["6² + 8² = 36 + 64 = 100.", "c = √100 = 10."]},
    },
    "Derivatives": {
        "explanation": [
            "A derivative measures how fast a function is changing.",
            "The power rule: the derivative of xⁿ is n·xⁿ⁻¹.",
            "You bring the exponent down as a coefficient and reduce it by one.",
            "Derivatives give slopes, speeds, and rates of change.",
        ],
        "worked_example": {
            "problem": "Differentiate f(x) = x³.",
            "steps": [
                "Apply the power rule: d/dx xⁿ = n·xⁿ⁻¹.",
                "Bring down the 3 and subtract 1 from the exponent: 3·x³⁻¹.",
                "f′(x) = 3x².",
            ],
        },
        "practice": {"problem": "Differentiate f(x) = x⁵."},
        "answer": {"steps": ["Power rule: 5·x⁵⁻¹.", "f′(x) = 5x⁴."]},
    },
    "Newton's Second Law": {
        "explanation": [
            "Newton's second law links force, mass, and acceleration.",
            "It states F = ma (force equals mass times acceleration).",
            "A larger force produces more acceleration for the same mass.",
            "A larger mass needs more force for the same acceleration.",
        ],
        "worked_example": {
            "problem": "A 2 kg cart accelerates at 3 m/s². Find the net force.",
            "steps": [
                "Use F = ma.",
                "Substitute: F = 2 kg × 3 m/s².",
                "F = 6 N.",
            ],
        },
        "practice": {"problem": "A 5 kg object accelerates at 4 m/s². Find the net force."},
        "answer": {"steps": ["F = ma = 5 kg × 4 m/s².", "F = 20 N."]},
    },
    "Kinematics": {
        "explanation": [
            "Kinematics describes motion without worrying about its causes.",
            "For constant acceleration, final velocity is v = u + at.",
            "Here u is the starting velocity, a the acceleration, and t the time.",
            "These equations predict where and how fast an object moves.",
        ],
        "worked_example": {
            "problem": "A car starts from rest and accelerates at 2 m/s² for 5 s. Find its final speed.",
            "steps": [
                "Use v = u + at, with u = 0.",
                "Substitute: v = 0 + 2 × 5.",
                "v = 10 m/s.",
            ],
        },
        "practice": {"problem": "Starting at 3 m/s, an object accelerates at 4 m/s² for 2 s. Find its final speed."},
        "answer": {"steps": ["v = u + at = 3 + 4 × 2.", "v = 11 m/s."]},
    },
    "Ohm's Law": {
        "explanation": [
            "Ohm's law relates voltage, current, and resistance in a circuit.",
            "It states V = IR (voltage equals current times resistance).",
            "More resistance means less current for the same voltage.",
            "It's the foundation of basic circuit analysis.",
        ],
        "worked_example": {
            "problem": "A 3 A current flows through a 4 Ω resistor. Find the voltage.",
            "steps": [
                "Use V = IR.",
                "Substitute: V = 3 A × 4 Ω.",
                "V = 12 V.",
            ],
        },
        "practice": {"problem": "A 2 A current flows through a 5 Ω resistor. Find the voltage."},
        "answer": {"steps": ["V = IR = 2 A × 5 Ω.", "V = 10 V."]},
    },
    "Arithmetic Mean": {
        "explanation": [
            "The arithmetic mean is the everyday 'average'.",
            "Add up all the values, then divide by how many there are.",
            "It summarizes a set of numbers with a single central value.",
            "Outliers can pull the mean up or down.",
        ],
        "worked_example": {
            "problem": "Find the mean of 4, 8, and 6.",
            "steps": [
                "Add the values: 4 + 8 + 6 = 18.",
                "Divide by the count (3): 18 ÷ 3.",
                "Mean = 6.",
            ],
        },
        "practice": {"problem": "Find the mean of 10, 20, 30, and 40."},
        "answer": {"steps": ["Sum: 10 + 20 + 30 + 40 = 100.", "Divide by 4: 100 ÷ 4 = 25."]},
    },
    "Probability": {
        "explanation": [
            "Probability measures how likely an event is, from 0 to 1.",
            "For equally likely outcomes, it's favorable outcomes ÷ total outcomes.",
            "A probability of 0 is impossible; 1 is certain.",
            "It underpins statistics, games, and risk.",
        ],
        "worked_example": {
            "problem": "A fair die is rolled. What is the probability of rolling a 4?",
            "steps": [
                "Favorable outcomes: just the 4 — that's 1.",
                "Total outcomes: 6.",
                "P = 1 ÷ 6 ≈ 0.17.",
            ],
        },
        "practice": {"problem": "A fair die is rolled. What is the probability of rolling an even number?"},
        "answer": {"steps": ["Favorable outcomes: 2, 4, 6 — that's 3.", "Total: 6.", "P = 3 ÷ 6 = 1/2."]},
    },
}

# Objective phrases -> canonical concept. Specific phrases first (first match
# wins); kept conservative so a miss falls back to the conceptual profile rather
# than mislabeling a problem.
_MATCHERS = {
    "Order of Operations": ("order of operations", "pemdas", "bodmas"),
    "Quadratic Equations": ("quadratic",),
    "Linear Equations": ("linear equation", "solve for x", "solving equations"),
    "Pythagorean Theorem": ("pythagorean", "pythagoras"),
    "Derivatives": ("derivative", "differentiate", "differentiation"),
    "Percentages": ("percentage", "percent"),
    "Newton's Second Law": ("newton's second law", "newtons second law", "f = ma", "f=ma"),
    "Kinematics": ("kinematic", "equations of motion", "projectile motion"),
    "Ohm's Law": ("ohm's law", "ohms law"),
    "Arithmetic Mean": ("arithmetic mean", "calculate the mean", "calculate the average", "compute the average"),
    "Probability": ("probability",),
}


def explanation_for(name):
    """Curated explanation bullets for a quantitative concept, or None."""
    entry = LIBRARY.get(name)
    return list(entry["explanation"]) if entry else None


def match(objective):
    """The canonical quantitative concept named in an objective, or None."""
    text = objective.lower()
    for name, phrases in _MATCHERS.items():
        if any(phrase in text for phrase in phrases):
            return name
    return None


def find_all(text):
    """Every quantitative concept named anywhere in a block of text (e.g. mined
    from a homework assignment), de-duplicated in match order."""
    lowered = text.lower()
    found = []
    for name, phrases in _MATCHERS.items():
        if name not in found and any(phrase in lowered for phrase in phrases):
            found.append(name)
    return found


def unit_for(name):
    """The full worked-problem unit for a concept, or None:
    {worked_example:{problem, steps}, practice:{problem}, answer:{steps}}."""
    entry = LIBRARY.get(name)
    if not entry or not all(k in entry for k in ("worked_example", "practice", "answer")):
        return None
    return {
        "worked_example": {
            "problem": entry["worked_example"]["problem"],
            "steps": list(entry["worked_example"]["steps"]),
        },
        "practice": {"problem": entry["practice"]["problem"]},
        "answer": {"steps": list(entry["answer"]["steps"])},
    }
