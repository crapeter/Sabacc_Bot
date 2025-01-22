import discord
from discord.ext import commands
import random
import os
from dotenv import load_dotenv

load_dotenv()

bot = commands.Bot(command_prefix='!', intents=discord.Intents.all())

# Define card suits and values
nums =[-10, -9, -8, -7, -6, -5, -4, -3, -2, -1, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10] 
deck = {
	'circles': [f"{num} of circles" for num in nums],
	'triangles': [f"{num} of triangles" for num in nums],
	'squares': [f"{num} of sqaures" for num in nums],
	'idiots': [True, True]
}
dealer_dice_rolls = []

# Game state variables
game_active = False
players = {}
hands = {}
rounds_played = {}
played_cards = set()
discarded_cards = set()
idiots_played = 0

@bot.event
async def on_ready():
	print(f"Logged in as {bot.user}")

@bot.command()
async def commands(ctx):
	help_message = ("**Sabacc Game Commands:**\n"
					"`!start` - Start a new game of Sabacc.\n"
					"`!join` - Join the current game.\n"
					"`!hand` - View your current hand.\n"
					"`!gain [discard: bool, True || False] [idx: int]` - Gain a card from the draw pile. Optionally discard a card from your hand.\n"
					"`!swap [idx: int]` - Swap a card with the top card from the discard pile.\n"
					"`!stand` - Stand and do nothing this turn.\n"
					"`!junk` - Discard all cards and exit the game.\n"
					"`!top_discard` - View the top card on the discard pile.\n"
					"`!score` - View your hands total score.\n"
					"`!end` - End the current game.")
	await ctx.send(help_message)

@bot.command()
async def start(ctx):
	global game_active, players, hands, played_cards, rounds_played, idiots_played, discarded_cards, dealer_dice_rolls
	if game_active:
		await ctx.send("A game is already in progress!")
		return

	# Initialize game state
	game_active = True
	players = {}
	hands = {}
	rounds_played = {}
	played_cards = set()
	discarded_cards = set()
	idiots_played = 0
	dealer_dice_rolls = []

	# Initialize dealer's dice rolls
	for _ in range(3):
		die_1 = random.randint(1, 6)
		die_2 = random.randint(1, 6)
		dealer_dice_rolls.append([die_1, die_2])

	await ctx.send("Sabacc game started! Use `!join` to enter the game.")
	await ctx.send(f"Dealer's dice rolls: " + ", ".join([f"|| {roll[0]}, {roll[1]} ||" for roll in dealer_dice_rolls]))

'''
Join: joins the game
'''
@bot.command()
async def join(ctx):
	global players, hands, played_cards, idiots_played
	if not game_active:
		await ctx.send("No game is currently active. Use `!start` to begin one.")
		return

	player = ctx.author
	if player.id in players:
		await ctx.send(f"{player.mention}, you are already in the game!")
		return
	
	if len(players) >= 6:
		await ctx.send("The game is full! Maximum of 6 players allowed.")
		return

	players[player.id] = player
	hands[player.id] = []
	rounds_played[player.id] = 0

	for _ in range(2):
		stave = random.choice(list(deck.keys()))
		card = random.choice(deck[stave])
		if isinstance(card, bool) and card:  # Check if the card is an Idiot
			hands[player.id].append("Idiot")
			idiots_played += 1
		else:
			hands[player.id].append(card)
			played_cards.add(card)

	await ctx.send(f"{player.mention} has joined the game!")

'''
Hand: displays the players current hand
'''
@bot.command()
async def hand(ctx):
	global played_cards
	player = ctx.author
	if player.id not in players:
		await ctx.send("You are not in the game! Use `!join` to participate.")
		return

	player_hand = hands[player.id]
	hand_message = "Your hand: " + ", ".join(player_hand)
	await player.send(hand_message)
	await ctx.send(f"{player.mention}, your hand has been sent via DM.")

"""
Gain: 
	take the top card from the draw pile. 
	you may keep the card or discard it
	If you pick the option of discarding, you must discard before you draw
"""
@bot.command()
async def gain(ctx, discard: bool = False, idx: int = None):
	global hands, played_cards, idiots_played, discarded_cards, rounds_played
	player = ctx.author
	if player.id not in players:
		await ctx.send("You are not in the game! Use `!join` to participate.")
		return

	if rounds_played[player.id] >= 3:
		await player.send("You have already taken 3 actions this round. Please stand or use another command. Use `!score` to view your score.")
		return

	if not isinstance(discard, bool):
		await player.send("Invalid discard option. Please specify `True` if you wish to discard.")
		return

	if discard and (idx is None or idx < 0 or idx >= len(hands[player.id])):
		await player.send("Invalid discard index. Please specify a valid index.")
		return
	elif discard and idx is not None:
		# Discard the specified card
		discarded_card = hands[player.id].pop(idx)
		discarded_cards.add(discarded_card)

	# Simulate drawing a card from the deck
	while True:
		stave = random.choice(list(deck.keys()))
		card = random.choice(deck[stave])
		if isinstance(card, bool) and card and idiots_played >= 2:
			continue
		if card not in played_cards or (card == "Idiot" and idiots_played < 2):
			if isinstance(card, bool) and card:  # Check if the card is an Idiot
				idiots_played += 1
				hands[player.id].append("Idiot")
			else:
				hands[player.id].append(card)
				played_cards.add(card)
			break
	
	await player.send(f"You drew a card: {hands[player.id][-1]}.\nYour current hand: {', '.join(hands[player.id])}")
	rounds_played[player.id] += 1

	if rounds_played[player.id] >= 3:
		await player.send("That was your last round, Use `!score` to view your score.")
		return

	if check_double(rounds_played[player.id] - 1):
		await player.send("The dealer rolled doubles! You will be dealt new cards. Use `!hand` to view your new hand.")
		rolled_double(player.id, hands[player.id])

"""
Swap: take the top card from the discard pile and place a card from your hand face up on the discard pile
"""
@bot.command()
async def swap(ctx, idx: int = None):
	global hands, played_cards, discarded_cards, rounds_played
	player = ctx.author
	if player.id not in players:
		await ctx.send("You are not in the game! Use `!join` to participate.")
		return

	if rounds_played[player.id] >= 3:
		await player.send("You have already taken 3 actions this round. Please stand or use another command. Use `!score` to view your score.")
		return

	if idx is None or idx < 0 or idx >= len(hands[player.id]):
		await player.send("Invalid index. Please specify a valid index.")
		return

	if not discarded_cards:
		await player.send("The discard pile is empty. Cannot swap.")
		return

	# Simulate taking the most recent card from the discard pile
	discarded_card = list(discarded_cards)[-1]
	hands[player.id].append(discarded_card)
	discarded_cards.remove(discarded_card)

	# Place the specified card from hand to discard pile
	card_to_discard = hands[player.id].pop(idx)
	discarded_cards.add(card_to_discard)
	rounds_played[player.id] += 1

	if rounds_played[player.id] >= 3:
		await player.send("That was your last round, Use `!score` to view your score.")
		return

	if check_double(rounds_played[player.id] - 1):
		await player.send("The dealer rolled doubles! You will be dealt new cards. Use `!hand` to view your new hand.")
		rolled_double(player.id, hands[player.id])

"""
Stand: you do nothing, stand if you do not wish to take a card or discard on this turn
"""
@bot.command()
async def stand(ctx):
	global rounds_played
	player = ctx.author
	if player.id not in players:
		await ctx.send("You are not in the game! Use `!join` to participate.")
		return

	if rounds_played[player.id] >= 3:
		await player.send("You have already taken 3 actions this round. Please stand or use another command. Use `!score` to view your score.")
		return

	await player.send("You chose to stand. No action taken this turn.")

	rounds_played[player.id] += 1

	if rounds_played[player.id] >= 3:
		await player.send("That was your last round, Use `!score` to view your score.")
		return

	if check_double(rounds_played[player.id] - 1):
		await player.send("The dealer rolled doubles! You will be dealt new cards. Use `!hand` to view your new hand.")
		rolled_double(player.id, hands[player.id])

"""
Junk
	if you feel you can't win with the cards in your hand then you can place all of your cards face up in the discard pile and exit the game
"""
@bot.command()
async def junk(ctx):
	global players, hands, discarded_cards, rounds_played
	player = ctx.author
	if player.id not in players:
		await ctx.send("You are not in the game! Use `!join` to participate.")
		return

	if rounds_played[player.id] >= 3:
		await player.send("You have already taken 3 actions this round. Please stand or use another command. Use `!score` to view your score.")
		return

	# Move all player's cards to the discard pile
	for card in hands[player.id]:
		discarded_cards.add(card)
	hands[player.id] = []

	players.pop(player.id, None)
	hands.pop(player.id, None)
	rounds_played.pop(player.id, None)
	await ctx.send(f"{player.mention} has junked their hand and exited the game.")

"""
Score: view the score of you deck
"""
@bot.command()
async def score(ctx):
	global hands
	player = ctx.author
	if player.id not in players:
		await ctx.send("You are not in the game! Use `!join` to participate.")
		return

	player_hand = hands[player.id]
	score = sum(int(card.split()[0]) for card in player_hand if card != "Idiot")
	await player.send(f"{player.mention}, your score is: {score}")

'''
Used to view the top card on the discard pile for the swap command
'''
@bot.command()
async def top_discard(ctx):
	global discarded_cards
	if not discarded_cards:
		await ctx.send("The discard pile is empty.")
		return

	top_discard = list(discarded_cards)[-1]
	await ctx.send(f"Top card on the discard pile: {top_discard}")

'''
End: ends the game and displays the winner
'''
@bot.command()
async def end(ctx):
	global game_active, players, hands, dealer_dice_rolls, rounds_played, played_cards, discarded_cards, idiots_played
	if not game_active:
		await ctx.send("No game is currently active.")
		return

	# Checks that all players have taken three turns
	if any(rounds_played[player_id] < 3 for player_id in players.keys()):
		await ctx.send("Not all players have finished their turns yet.")
		return

	# Goes through the players and prints the score of each player
	scores = {player: sum(int(card.split()[0]) for card in hands[player] if card != "Idiot") for player in players}
	await ctx.send("Game results:\n" + "\n".join([f"{players[player].mention} has a score of: {score}" for player, score in scores.items()]))

	# Prints the winner, the winner is the one closest to zero
	closest_score = min(abs(score) for score in scores.values())
	winners = [player for player, score in scores.items() if abs(score) == closest_score]

	if len(winners) == 1:
		winner = winners[0]
		await ctx.send(f"The winner is: {players[winner].mention} with a score of {scores[winner]}!")
	else:
		roll_results = {player: random.randint(1, 100) for player in winners}
		highest_roll = max(roll_results.values())
		roll_winners = [player for player, roll in roll_results.items() if roll == highest_roll]

		while len(roll_winners) > 1:
			roll_results = {player: random.randint(1, 100) for player in roll_winners}
			highest_roll = max(roll_results.values())
			roll_winners = [player for player, roll in roll_results.items() if roll == highest_roll]

		winner = roll_winners[0]
		await ctx.send(
			f"Tiebreaker rollies! {', '.join(f'{players[p].mention}: {roll}' for p, roll in roll_results.items())}\n"
			f"The winner is: {players[winner].mention} with a roll of {highest_roll}!"
		)

	for _, v in players.items():
		await v.send(f"--------------------------------------------")

	# Resets the game state
	game_active = False
	players = {}
	hands = {}
	dealer_dice_rolls = []
	rounds_played = {}
	played_cards = set()
	discarded_cards = set()
	idiots_played = 0
	await ctx.send("Game ended! Thanks for playing.")

'''
Checks if the dealer rolled doubles
'''
def check_double(idx):
	# Check if the dealer rolled doubles
	rolls = dealer_dice_rolls[idx]
	return rolls[0] == rolls[1]

'''
If the dealer rolls doubles,
all players cards ar placed in the discard pile,
the dealer then deall new cards to all players,
each player receives the same amount of cards that they discarded
'''
def rolled_double(player_id, cards):
	global hands, discarded_cards, idiots_played, played_cards
	total_cards = len(cards)

	for card in hands[player_id]:
		discarded_cards.add(card)
	hands[player_id] = []

	for _ in range(total_cards):
		while True:
			stave = random.choice(list(deck.keys()))
			card = random.choice(deck[stave])
			if isinstance(card, bool) and card and idiots_played >= 2:
				continue
			if card not in played_cards or (card == "Idiot" and idiots_played < 2):
				if isinstance(card, bool) and card:  # Check if the card is an Idiot
					idiots_played += 1
					hands[player_id].append("Idiot")
				else:
					hands[player_id].append(card)
					played_cards.add(card)
			if len(hands[player_id]) == total_cards:
				return
		

bot.run(os.getenv("DISCORD_TOKEN"))
