from brain import load_brain, add_rule


def process_feedback(user_input, response, quality):
    brain = load_brain()

    # if quality low → learn
    if quality < 0.5:
        rule = "Avoid vague responses. Be more direct and actionable."
        add_rule(brain, rule)

    # if quality high → reinforce
    if quality > 0.8:
        rule = "Maintain strong clarity and confident tone."
        add_rule(brain, rule)