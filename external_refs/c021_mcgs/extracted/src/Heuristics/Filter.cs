using System;
using System.Collections.Generic;
using SabberStoneCoreAi.MCGS.SabberHelper;
using SabberStoneCoreAi.MCGS.SabberHelper.Option;
using SabberStoneCoreAi.MCGS.Utils;
using SabberStoneCore.Model;
using SabberStoneCore.Model.Entities;

namespace SabberStoneCoreAi.MCGS.Heuristics
{
	internal delegate void OptionsFilter(Game game, Options options);

	public static class Filters
	{
		internal static void CategoryBasedFilter(Game g, Options options)
		{
			Controller c = g.CurrentPlayer;

			// Filtering PlayCardOptions
			for (int j = options.PlayCardOptions.Count - 1; j >= 0; j--)
			{
				PlayCardOption playCardOption = options.PlayCardOptions[j];
				int id = playCardOption.Source.Card.AssetId;
				if (playCardOption.HasTargets)
				{
					List<int> indicesToBeRemoved = new List<int>();
					ICharacter[] targets = playCardOption.Targets;
					if (CardCategory.CardsHarmfulToTarget.Contains(id))
					{
						int currentId = c.Id;
						for (int i = 0; i < targets.Length; i++)
							if (targets[i]?.Controller.Id == currentId)
								indicesToBeRemoved.Add(i);
					}
					else if (CardCategory.BeneficialToTarget.Contains(id))
					{
						int currentOpId = g.CurrentOpponent.Id;
						for (int i = 0; i < targets.Length; i++)
							if (targets[i]?.Controller.Id == currentOpId)
								indicesToBeRemoved.Add(i);
					}
					else if (CardCategory.RestoreOnly.Contains(id) && !g.CurrentPlayer.RestoreToDamage)
					{
						for (int i = 0; i < targets.Length; i++)
							if (targets[i]?.Damage == 0)
								indicesToBeRemoved.Add(i);
					}

					if (indicesToBeRemoved.Count > 0)
					{
						if (indicesToBeRemoved.Count == targets.Length)
						{
							options.PlayCardOptions.RemoveAt(j);
							continue;
						}

						ICharacter[] newTargets = targets.RemoveAtIndices(indicesToBeRemoved.ToArray());
						options.PlayCardOptions[j] = playCardOption.ChangeTargets(newTargets);
						//options.PlayCardOptions.SetValue(j, playCardOption.ChangeTargets(newTargets));
					}
				}
				else
				{
					if (CardCategory.MinionAreaOfEffectSpells.Contains(id) &&
					    g.CurrentOpponent.BoardZone.Count == 0)
						options.PlayCardOptions.RemoveAt(j);
					else if (CardCategory.MyMinionsSpells.Contains(id) &&
					         c.BoardZone.Count == 0)
						options.PlayCardOptions.RemoveAt(j);
				}
			}

			// Filtering HeroPowerOption
			if (options.IsHeroPowerUseable && options.HeroPowerOption.Targets != null)
			{
				int id = c.Hero.HeroPower.Card.AssetId;
				ICharacter[] targets = options.HeroPowerOption.Targets;
				List<int> indicesToBeRemoved = new List<int>();
				if (CardCategory.PowersHarmfulToTarget.Contains(id))
				{
					int currentId = c.Id;

					for (int i = 0; i < targets.Length; i++)
						if (targets[i].Controller.Id == currentId)
							indicesToBeRemoved.Add(i);
				}
				else if (id == 479 && !c.RestoreToDamage)
				{
					for (int i = 0; i < targets.Length; i++)
						if (targets[i].Damage == 0)
							indicesToBeRemoved.Add(i);
				}

				if (indicesToBeRemoved.Count > 0)
				{
					if (indicesToBeRemoved.Count == targets.Length)
					{
						options.IsHeroPowerUseable = false;
						return;
					}

					for (int i = 0; i < indicesToBeRemoved.Count; i++)
						targets[indicesToBeRemoved[i]] = null;

					var newTargets = new ICharacter[targets.Length - indicesToBeRemoved.Count];
					for (int i = 0, k = 0; i < targets.Length; i++)
						if (targets[i] != null)
							newTargets[k++] = targets[i];

					options.HeroPowerOption = options.HeroPowerOption.ChangeTargets(newTargets);
				}
			}
		}

		internal static void CompulsiveAttackWhenAvailable(Game g, Options options)
		{
			if (options.EndTurnTaskRemoved)
				return;

			if (options.AttackOptions == null) return;

			foreach (AttackOption option in options.AttackOptions)
			{
				if (option.Source == null) continue;

				if (!option.IsHeroValidTarget) continue;

				options.EndTurnTaskRemoved = true;
				return;
			}
		}

		internal static void CompulsiveHeroPowerWhenAvailable(Game g, Options options)
		{
			if (options.EndTurnTaskRemoved)
				return;

			if (!options.IsHeroPowerUseable)
				return;

			int id = g.CurrentPlayer.Hero.HeroPower.Card.AssetId;

			// Exclude Life Tap
			if (id == 300)
				return;

			// Ignore Lesser Heal
			if (id == 479 && !g.CurrentPlayer.RestoreToDamage || !g.CanOpponentBeAttacked())
				return;

			options.EndTurnTaskRemoved = true;
		}

		internal static void RemoveVoidAction(Game g, Options options)
		{
			//var toBeRemoved = new List<PlayerTask>();
			var found = false;
			var flag = false;
			//var comboFlag = false;

			Controller c = g.CurrentPlayer;

			for (int i = options.PlayCardOptions.Count - 1; i >= 0; i--)
			{
				int id = options.PlayCardOptions[i].Source.Card.AssetId;

				// Mana boosting cards
				if (CardCategory.GainFullCrystals.BinarySearch(id) >= 0)
				{
					if (flag)
					{
						if (!found)
						{
							options.PlayCardOptions.RemoveAt(i);
						}
					}
					else
					{
						flag = true;
						int mana = c.RemainingMana;
						if (mana == 10) continue;

						ReadOnlySpan<IPlayable> hand = c.HandZone.GetSpan();

						for (int j = 0; j < hand.Length; j++)
						{
							int cost = hand[j].Cost;
							if (mana < cost && cost <= mana + 1)
							{
								found = true;
								break;
							}
						}

						if (found) continue;

						options.PlayCardOptions.RemoveAt(i);

						continue; // Each category in here is mutually disjoint
					}
				}

				// Remove suicidal cards
				if (CardCategory.CardsCanHarmOwnHero.TryGetValue(id, out var info) &&
				    c.Hero.Health + c.Hero.Armor <= info.amount)
				{
					options.PlayCardOptions.RemoveAt(i);
					continue;
				}

				// Obliterate
				if (id == 43120)
				{
					int total = c.Hero.Health + c.Hero.Armor;

					//var list = options.PlayCardOptions[i].Targets.ToList();
					//list.RemoveAll(t => t.Health >= total);

					var newTargets = options.PlayCardOptions[i].Targets.FilterSmallArray(p => p.Health < total);

					if (newTargets.Length == 0)
					{
						options.PlayCardOptions.RemoveAt(i);
						continue;
					}

					options.PlayCardOptions[i] = options.PlayCardOptions[i]
						.ChangeTargets(newTargets);
					//options.PlayCardOptions.SetValue(i, options.PlayCardOptions[i].ChangeTargets(newTargets));
				}
			}


			//for (int i = 0; i < options.AttackOptions[i].Count; i++)
			//{
			//    if (options.AttackOptions[i].Source == null) continue;

			//    int hp = c.Hero.Health + c.Hero.Armor;

			//    var filtered = options.AttackOptions[i].Targets.FilterSmallArray(m => m.AttackDamage < hp);

			//    options.AttackOptions[i] = options.AttackOptions[i].ChangeTargets(filtered);

			//    break;
			//}

			if (options.IsHeroPowerUseable)
			{
				// Life Tap
				if (c.Hero.HeroPower.Card.AssetId == 300)
				{
					if (c.Hero.Health + c.Hero.Armor <= 2)
						options.IsHeroPowerUseable = false;
					else if (c.DeckZone.IsEmpty)
						options.IsHeroPowerUseable = false;
				}
			}
		}
	}
}
