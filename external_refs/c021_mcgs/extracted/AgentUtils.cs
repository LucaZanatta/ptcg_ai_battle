using System;
using System.Collections.Generic;
using SabberStoneCore.Enums;
using SabberStoneCore.Model;
using SabberStoneCore.Model.Entities;
using SabberStoneCore.Model.Zones;
using SabberStoneCoreAi.Meta;

namespace SabberStoneCoreAi.MCGS
{
	internal static class AgentUtils
	{
		private const int BUFFER_SIZE = 30;
		private static readonly Dictionary<int, (Card, int)> WarriorDeck;
		private static readonly Dictionary<int, (Card, int)> MageDeck;
		private static readonly Dictionary<int, (Card, int)> ShamanDeck;
		private static readonly IPlayable[] _entityBuffer = new IPlayable[BUFFER_SIZE];

		internal static readonly Random _rnd = new Random();

		internal static void Shuffle<T>(this Span<T> span, Random rnd)
		{
			for (int i = 0; i < span.Length; i++)
			{
				int r = rnd.Next(i, span.Length);
				T temp = span[i];
				span[i] = span[r];
				span[r] = temp;
			}
		}

		internal static Game GenerateGameForSimulation(POGame.POGame poGame)
		{
			Controller op = poGame.CurrentOpponent;
			Dictionary<int, (Card, int)> opDeck;
			switch (op.HeroClass)
			{
				case CardClass.WARRIOR:
					opDeck = WarriorDeck;
					break;
				case CardClass.MAGE:
					opDeck = MageDeck;
					break;
				case CardClass.SHAMAN:
					opDeck = ShamanDeck;
					break;
				default:
					opDeck = GenerateRandomDeck(op.HeroClass, op.Game.FormatType);
					break;
			}

			var observedCards = new Dictionary<int, int>(10);
			//int numMageSpellObserved = 0;
			foreach (IPlayable entity in op.GraveyardZone)
			{
				if (entity.Id > 67)
					continue;
				int key = entity.Card.AssetId;

				if (observedCards.ContainsKey(key))
					observedCards[key]++;
				else
					observedCards.Add(key, 1);

				//if (!opDeck.ContainsKey(key) && key != (int) 2997)
				//{
				//	Card card = Cards.FromAssetId(key);
				//	if (card.Class == CardClass.MAGE && card.Type == CardType.SPELL)
				//		numMageSpellObserved++;
				//}
			}

			var span = op.BoardZone.GetSpan();
			for (int i = 0; i < span.Length; i++)
			{
				if (span[i].Id > 67)
					continue;
				int key = span[i].Card.AssetId;

				if (observedCards.ContainsKey(key))
					observedCards[key]++;
				else
					observedCards.Add(key, 1);
			}

			var opDeckEntities = new Span<IPlayable>(_entityBuffer);

			Game game = op.Game.Clone();
			op = game.CurrentOpponent;

			int k = 0;
			foreach ((int key, (Card card, int count)) in opDeck)
			{
				int c = count;
				if (observedCards.TryGetValue(key, out int observedCount))
					c -= observedCount;
				switch (c)
				{
					case 0:
						continue;
					case 1:
						opDeckEntities[k++] = Entity.FromCard(in op, in card);
						break;
					case 2:
						opDeckEntities[k] = Entity.FromCard(in op, in card);
						opDeckEntities[k + 1] = Entity.FromCard(in op, in card);
						k += 2;
						break;
					default:
						//throw new Exception();
						continue;
				}
			}

			if (observedCards.ContainsKey((int)CardIds.Forgotten_Torch))
				opDeckEntities[k++] = Entity.FromCard(in op, in CardLib.RoaringTorch);


			bool coin = observedCards.ContainsKey((int) CardIds.The_Coin);

			opDeckEntities = opDeckEntities.Slice(0, k);
			opDeckEntities.Shuffle(_rnd);

			var handZone = new HandZone(op);
			var deckZone = new DeckZone(op);

			int j = 0;
			int handCountToFill = op.HandZone.Count;
			if (coin)
			{
				handCountToFill -= 1;
				handZone.Add(Entity.FromCard(in op, in CardLib.TheCoin));
			}
			//if (numMageSpellObserved == 0 && observedCards.ContainsKey((int) CardIds.Babbling_Book))
			//{
			//	handCountToFill -= 1;
			//	var spell = Entity.FromCard(in op, CardCategory.GetRandomMageSpell(_rnd));
			//	spell[GameTag.]
			//	handZone.Add();
			//	numMageSpellObserved++;
			//}
			//if (numMageSpellObserved == 0 && observedCards.ContainsKey((int) CardIds.Tomb_of_Intellect))
			//{
			//	handCountToFill -= 1;
			//	handZone.Add(Entity.FromCard(in op, CardCategory.GetRandomMageSpell(_rnd)));
			//	numMageSpellObserved++;
			//}

			for (; j < handCountToFill; j++)
				handZone.Add(opDeckEntities[j]);

			for (; j < opDeckEntities.Length; j++)
				deckZone.Add(opDeckEntities[j]);

			int delta = op.DeckZone.Count - deckZone.Count;
			var allRandom = Cards.FormatTypeClassCards(game.FormatType)[op.HeroClass];
			while (delta > 0)
			{
				var randEntity = Entity.FromCard(in op, allRandom[_rnd.Next(allRandom.Count)]);
				randEntity[GameTag.PUZZLE] = 1;
				deckZone.Add(randEntity);
				delta--;
			}

			op.HandZone = handZone;
			op.DeckZone = deckZone;

			Array.Clear(_entityBuffer, 0, BUFFER_SIZE);

			return game;
		}

		//private static void InvestigateHistory(Controller op, int historyOffset, int graveyardOffset)
		//{
		//	op.NumCardsDrawnThisTurn

		//	List<PlayHistoryEntry> history = op.PlayHistory;
		//	GraveyardZone graveyard = op.GraveyardZone;

		//	int mageSpells = 0;
		//	for (int i = historyOffset; i < history.Count; i++)
		//	{
		//		switch ((CardIds)history[i].SourceCard.AssetId)
		//		{
		//			case CardIds.Babbling_Book:
		//			case CardIds.Tomb_of_Intellect:
		//			case CardIds.Lesser_Ruby_Spellstone:
		//			case CardIds.Primordial_Glyph when op.HeroClass == CardClass.MAGE:
		//				mageSpells++;
		//				break;
		//			case CardIds.Ruby_Spellstone:
		//				mageSpells += 2;
		//				break;
		//			case CardIds.Greater_Ruby_Spellstone:
		//			case CardIds.Cabalists_Tomb:
		//				mageSpells += 3;
		//				break;

		//		}
		//	}
		//}

		internal static (SearchConfig, SearchConfig) GetConfig(POGame.POGame poGame)
		{
			SearchConfig myConfig;
			SearchConfig opConfig;
			switch (poGame.CurrentPlayer.HeroClass)
			{
				case CardClass.WARRIOR:
					myConfig = SearchConfig.WarriorConfig;
					break;
				case CardClass.MAGE:
					myConfig = SearchConfig.MageConfig;
					break;
				case CardClass.SHAMAN:
					myConfig = SearchConfig.ShamanConfig;
					break;
				case CardClass.PALADIN:
					myConfig = SearchConfig.PaladinConfig;
					break;
				default:
					myConfig = SearchConfig.BaseConfig;
					break;
			}
			switch (poGame.CurrentOpponent.HeroClass)
			{
				case CardClass.WARRIOR:
					opConfig = SearchConfig.WarriorConfig;
					break;
				case CardClass.MAGE:
					opConfig = SearchConfig.MageConfig;
					break;
				case CardClass.SHAMAN:
					opConfig = SearchConfig.ShamanConfig;
					break;
				case CardClass.PALADIN:
					opConfig = SearchConfig.PaladinConfig;
					break;
				default:
					opConfig = SearchConfig.BaseConfig;
					break;
			}

			return (myConfig, opConfig);
		}

		static AgentUtils()
		{
			var dict = new Dictionary<int, (Card, int)>(20);
			foreach (Card card in Decks.AggroPirateWarrior)
			{
				int key = card.AssetId;
				if (dict.ContainsKey(key))
					dict[key] = (card, 2);
				else
					dict.Add(key, (card, 1));
			}
			WarriorDeck = dict;
			dict = new Dictionary<int, (Card, int)>(20);
			foreach (Card card in Decks.RenoKazakusMage)
			{
				int key = card.AssetId;
				if (dict.ContainsKey(key))
					dict[key] = (card, 2);
				else
					dict.Add(key, (card, 1));
			}
			MageDeck = dict;
			dict = new Dictionary<int, (Card, int)>(20);
			foreach (Card card in Decks.MidrangeJadeShaman)
			{
				int key = card.AssetId;
				if (dict.ContainsKey(key))
					dict[key] = (card, 2);
				else
					dict.Add(key, (card, 1));
			}
			ShamanDeck = dict;
		}

		enum CardIds
		{
			The_Coin = 1746,

			Forgotten_Torch = 2874,
			Roaring_Torch = 2997,

			Babbling_Book = 39169,
			Tomb_of_Intellect = 52262,
			Lesser_Ruby_Spellstone = 43414,
			Ruby_Spellstone = 43412,
			Greater_Ruby_Spellstone = 43411,
			Cabalists_Tomb = 38418,
			Shimmering_Tempest = 41927,

			Primordial_Glyph = 41496,

			Netherspite_Historian = 39554,
		}

		private static Dictionary<int, (Card, int)> GenerateRandomDeck(CardClass cls, FormatType fmt)
		{
			IReadOnlyList<Card> list = Cards.FormatTypeClassCards(fmt)[cls];
			var result = new Dictionary<int, (Card, int)>(20);
			int count = 0;
			do
			{
				var randCard = list[_rnd.Next(list.Count)];
				if (result.TryGetValue(randCard.AssetId, out var value))
				{
					if (randCard.Rarity == Rarity.LEGENDARY || value.Item2 == 2)
						continue;
					result[randCard.AssetId] = (randCard, 2);
				}
				else
				{
					result.Add(randCard.AssetId, (randCard, 1));
				}

				count++;
			} while (count < 30);

			return result;
		}

		private static class CardLib
		{
			public static readonly Card RoaringTorch = Cards.FromId("LOE_002t");
			public static readonly Card TheCoin = Cards.FromId("GAME_005");
		}
	}
}
