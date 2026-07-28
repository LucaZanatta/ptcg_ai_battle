using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;
using SabberStoneCoreAi.MCGS.Utils;
using SabberStoneCore.Enums;
using SabberStoneCore.Model;
using SabberStoneCore.Model.Entities;

namespace SabberStoneCoreAi.MCGS.Heuristics
{
    public static partial class CardCategory
    {
        private static readonly CultureInfo _ci = new CultureInfo("en");

        //public static readonly Card[] allStandardWithNonCollectibles;

        /// <summary>
        /// This category of card should target one of the enemies.
        /// </summary>
        public static readonly HashSet<int> CardsHarmfulToTarget;

        /// <summary>
        /// This category of hero power should target one of the enemies.
        /// </summary>
        public static readonly HashSet<int> PowersHarmfulToTarget;

        /// <summary>
        /// This category of card should target one of the allies.
        /// </summary>
        public static readonly HashSet<int> BeneficialToTarget;

        /// <summary>
        /// This category of card should not be used when the opponent's board is empty.
        /// </summary>
        public static readonly HashSet<int> MinionAreaOfEffectSpells;

        /// <summary>
        /// This category of card should be used when the player's board is not empty.
        /// </summary>
        public static readonly HashSet<int> MyMinionsSpells;

        /// <summary>
        /// This category of card gives player full mana crystal(s).
        /// </summary>
        public static readonly List<int> GainFullCrystals = new List<int>();

        /// <summary>
        /// This category of card tries to get a card(s) from player's deck.
        /// </summary>
        public static readonly List<int> GetFromDeck = new List<int>();

        /// <summary>
        /// This category of card gives enchantment to adjacent minions.
        /// </summary>
        public static readonly HashSet<int> AdjacentEffectMinions;

        ////	TODO
        //public static readonly HashSet<int> AffectAdjacentMinions;

        /// <summary>
        /// This category of card only has restoring effect.
        /// </summary>
        public static readonly HashSet<int> RestoreOnly;

        /// <summary>
        /// This category of card has opponent hand related random effect.
        /// </summary>
        public static readonly List<int> RandomOpponentHand = new List<int>();

        /// <summary>
        /// This category of card reveals top N cards of player's deck.
        /// </summary>
        public static readonly HashSet<int> RevealTopDeckCards = new HashSet<int>();

        /// <summary>
        /// This category of card can deal direct damage to opponent's hero.
        /// </summary>
        public static readonly SortedDictionary<int, (int amount, bool spelldmg)> CanDealFaceDamage = new SortedDictionary<int, (int amount, bool spelldmg)>();

        /// <summary>
        /// This category of card can deal direct damage to opponent's hero without targeting it.
        /// </summary>
        public static readonly SortedDictionary<int, int> PowersCanDealDirectDamage = new SortedDictionary<int, int>();

        /// <summary>
        /// This category of card can return the target to hand from board.
        /// </summary>
        public static readonly HashSet<int> ReturnToHand = new HashSet<int>();

        ////  TODO
        //public static readonly HashSet<int> SilenceEffects = new HashSet<int>();

        public static readonly HashSet<int> SpellTriggers = new HashSet<int>();

        /// <summary>
        /// This category of card can destroy opponent's minions.
        /// </summary>
        public static readonly HashSet<int> HarmfulDeathrattles;

        ////  TODO: more void cards
        //public static readonly Dictionary<int, Func<Game, bool>> DoNothingables = new Dictionary<int, Func<Game, bool>>();

        public static readonly Dictionary<int, (int amount, bool spelldmg)> CardsCanHarmOwnHero;

        static CardCategory()
        {
            #region categories
            var allStandardWithNonCollectibles = Cards.All
                .Where(c => Cards.StandardSets.Contains(c.Set) && c.Type != CardType.ENCHANTMENT).ToArray();


            var harms = allStandardWithNonCollectibles.Where(p =>
            {
                var text = p.Text ?? "";
                return (p.Type == CardType.MINION || p.Type == CardType.SPELL) && 
                       p.CanRequireTarget() && 
                       (TextContains(text, "deal") || TextContains(text, "destroy")) && 
                       !((TextContains(p.Text, "random") || TextContains(p.Text, "all") || TextContains(p.Text, "Friendly")));
            }).Select(c => c.AssetId).ToList();
            var harmfulExceptions = new[]
            {
                45195,	//	Carnivorous Cube
	            43128,	//	Dark Pact
				42648,  //  Toxic Arrow
                163     //  Sacrificial Pact
            };
            var harmfulAddition = new[]
            {
                141
            };

            foreach (var exception in harmfulExceptions)
                harms.Remove(exception);

            harms.AddRange(harmfulAddition);

            CardsHarmfulToTarget = new HashSet<int>(harms);


            //PowersHarmfulToTarget = allStandardWithNonCollectibles.Where(p =>
            //{
            // var text = p.Text ?? "";
            // return p.Type == CardType.HERO_POWER;
            //})
            //PowersHarmfulToTarget.Sort();
            var powers = allStandardWithNonCollectibles.Where(p => p.Type == CardType.HERO_POWER && p.RequiresTarget && TextContains(p.Text, "deal")).Select(p => p.AssetId).ToList();
            PowersHarmfulToTarget = new HashSet<int>(powers);


            BeneficialToTarget = new HashSet<int>(allStandardWithNonCollectibles.Where(p =>
            {
                var text = p.Text ?? "";
                return p.CanRequireTarget() && (TextContains(text, "give") || TextContains(text, "restore"))
                                            && !((TextContains(text, "all") || TextContains(text, "random") ||
                                                  TextContains(text, "friendly") || TextContains(text, "your minions") ||
                                                  TextContains(text, "C'Thun") || TextContains(text, "deal") ||
                                                  TextContains(text, "destroy")));
            }).Select(c => c.AssetId));

            MinionAreaOfEffectSpells = new HashSet<int>(allStandardWithNonCollectibles.Where(p =>
            {
                var text = p.Text ?? "";
                return p.Type == CardType.SPELL
                       && (TextContains(text, "all") && TextContains(text, "minions"))
                       && !(TextContains(text, "summon") || TextContains(text, "hand"));
            }).Select(c => c.AssetId));
            var aoeExcpetions = new[]
            {
                1362,   //  Circle of Healing
                1366    //  Mass Dispel
            };
            foreach (var exception in aoeExcpetions)
                MinionAreaOfEffectSpells.Remove(exception);
            MinionAreaOfEffectSpells.Add(41871);    //  Corrupting Mist (used word "every" insted of "all")


            MyMinionsSpells = new HashSet<int>(allStandardWithNonCollectibles.Where(p =>
            {
                var text = p.Text ?? "";
                return p.Type == CardType.SPELL
                       && (TextContains(text, "your minions") /*&& !p.Tags.ContainsKey(GameTag.SECRET)*/);
            }).Select(c => c.AssetId));
            var myMinionExceptions = new[]
            {
                1026,   //  Commanding Shout
                41868,  //  The Last Kaleidosaur
                41221   //  Crystal Core
            };
            //  Wisps of the Old Gods, Power of the Wild
            foreach (var exception in myMinionExceptions)
                MyMinionsSpells.Remove(exception);

            GainFullCrystals.Add(1746);     //  The Coin
            GainFullCrystals.Add(40437);    //  Counterfeit Coin
            GainFullCrystals.Add(254);      //  Innerrvate
            //GainManaCrystals.Add(451);      //  Nourish(a)
            GainFullCrystals.Sort();


            //  TODO: GetFromDeck


            AdjacentEffectMinions = new HashSet<int>(allStandardWithNonCollectibles.Where(p =>
            {
                var text = p.Text ?? "";
                return p.Type == CardType.MINION && TextContains(text, "adjacent");
            }).Select(c => c.AssetId));


            RestoreOnly = new HashSet<int>(allStandardWithNonCollectibles.Where(p =>
            {
                var text = p.Text ?? "";
                return p.CanRequireTarget() && (p.Type == CardType.SPELL || p.Type == CardType.HERO_POWER) &&
                       TextContains(text, "restore");
            }).Select(p => p.AssetId));
            var restoreExceptions = new[]
            {
                43128,	//	Dark Pact
                149,    //  Ancestral Healing
                163,    //  Sacrificial Pact
                919,    //  Drain Life
                1100,   //  Siphon Soul
                1365,   //  Holy Fire
                41521,  //  Tidal Surge
                41170   //  Binding Heal
            };
            foreach (int exception in restoreExceptions)
                RestoreOnly.Remove(exception);
            //BenefitialToTarget = BenefitialToTarget.Except(RestoreOnly).ToList(); ??

            RandomOpponentHand = new List<int>
            {
                1099,       //  Mind Vision
                41567,      //  Dirty Rat
                42784       //  Skulking Giest
            };


            var topCards = allStandardWithNonCollectibles.Where(p =>
            {
                var text = p.Text ?? "";
                return
                    TextContains(text, "top") && TextContains(text, "your") && TextContains(text, "deck");
            });
            foreach (var card in topCards)
                RevealTopDeckCards.Add(card.AssetId);


            var faceDmgWT = allStandardWithNonCollectibles.Where(p =>
            {
                var text = p.Text ?? "";
                return
                    p.CanRequireTarget()
                    && TextContains(text, "deal") && TextContains(text, "damage")
                    && !TextContains(text, "minion");
            }).ToDictionary(p => p.AssetId, p =>
            {
                var text = p.Text;
                Int32.TryParse(Regex.Match(text, @"\d+").Value, out int amount);
                var spelldmg = text.Contains("spelldmg") && !(p.Type == CardType.HERO_POWER);
                return (amount, spelldmg);
            });
            var ddwtAdditions = new Dictionary<int, (int amount, bool spellDmg)>
            {
                { 41126, (2, false) }  //  Dispatch Kodo
            };
            var ddwtExceptions = new List<int>
            {
                435,    //  Holy Wrath
                974    //  Soulfire      Can throw errors for now
                //45975,  //  Spectral Pillager   //  calculation needed
            };
            foreach (var addition in ddwtAdditions)
                faceDmgWT.Add(addition.Key, addition.Value);
            foreach (var exception in ddwtExceptions)
                faceDmgWT.Remove(exception);
            foreach (var item in faceDmgWT)
                CanDealFaceDamage.Add(item.Key, item.Value);


            //var debug = CanDealDirectDamageWT.Select(p => (Cards.FromAssetId(p.Key).Name, p.Value)).ToList();

            //CanDealDirectDamageWOT = allStandardWithNonCollectibles.Where(p =>
            //{
            //    var text = p.Text ?? "";
            //    return
            //        !p.CanRequireTarget() && !p.Tags.Keys.Contains(GameTag.SECRET) &&
            //        !TextContains(text, "minion") && !TextContains(text, "Deathrattle") &&
            //        TextContains(text, "deal") && TextContains(text, "damage")  &&
            //        (TextContains(text, "hero") || (TextContains(text, "all enemies") && !TextContains(text, "split")));

            //}).ToDictionary(p => p.AssetId, p =>
            //{
            //    var text = p.Text;
            //    int amount = 0;
            //    Int32.TryParse(Regex.Match(text, @"\d+").Value, out amount);
            //    var spelldmg = text.Contains("spelldmg");
            //    return (amount, spelldmg);
            //});

            // Cards that deal direct face damage without targeting
            var faceDmgWOT = new Dictionary<int, (int amount, bool spellDmg)>
            {
                { 841, (2, true) },         //  Holy Nova
                { 710, (3, true) },         //  Sinister Strike
                { 545, (5, true) },         //  Mind Blast
                { 708, (2, true) },         //  Headcrack
                { 670, (4, false) },        //  Nightblade
                { 46194, (3, true) },       //  Death and Decay
                { 41335, (6, false) }      //  Invocation of Fire
                //{ 41309, (2, false) },    //  Emerald Reaver      Can cause suicidal action?
                //  should add cards that deals damage to all characters
            };
            foreach (var item in faceDmgWOT)
                CanDealFaceDamage.Add(item.Key, item.Value);

            // Powers that deal direct face damage
            var pdd = allStandardWithNonCollectibles.Where(p =>
            {
                var text = p.Text ?? "";
                return
                    p.Type == CardType.HERO_POWER
                    && TextContains(text, "deal") && TextContains(text, "damage")
                    && !TextContains(text, "minion");
            }).ToDictionary(p => p.AssetId, p =>
            {
                var text = p.Text;
                Int32.TryParse(Regex.Match(text, @"\d+").Value, out int amount);
                return amount;
            });
            foreach (var item in pdd)
                PowersCanDealDirectDamage.Add(item.Key, item.Value);


            ReturnToHand = new HashSet<int>
            {
                365,        //  Shadowstep
                40696,      //  Gadgetzan Ferryman
                461,        //  Sap
                287,        //  Kidnapper
                415,        //  Youthful Brewmaster
                186         //  Ancient Brewmaster
            };


            var spellTriggers =
                allStandardWithNonCollectibles.Where(p =>
                {
                    var text = p.Text ?? "";
                    return
                        p.Type == CardType.MINION
                        //&& !p.Tags.ContainsKey(GameTag.BATTLECRY)
                        //&& !p.Tags.ContainsKey(GameTag.DEATHRATTLE)
                        && TextContains(text, "you cast")
                        && (TextContains(text, "whenever") || TextContains(text, "after"));
                }).Select(p => p.AssetId).ToList();
            spellTriggers.Add(39426);       //  Arcane Giant
            spellTriggers.Remove(1667);     //  Lorewalker Cho
            spellTriggers.Remove(41913);    //  The Voraxx
            SpellTriggers = new HashSet<int>(spellTriggers);


            //DoNothingables = new Dictionary<int, Func<Game, bool>>
            //{
            //    { 41169, g => g.CurrentPlayer.DeckZone.Count(p => p.Card.Type == CardType.SPELL) != 0 },    //  Shadow Visions
            //    { 42804, g => g.CurrentPlayer.DeckZone.Count(p => p.Card.Type == CardType.MINION) != 0 }   //  Shadow Essence
            //};

            CardsCanHarmOwnHero =
                allStandardWithNonCollectibles
                    .Where(p =>
                    {
                        var text = p.Text ?? "";

                        return
                            (p.Tags.ContainsKey(GameTag.BATTLECRY) || p.Type == CardType.SPELL) &&
                            (TextContains(text, "damage to your hero") ||
                            TextContains(text, "damage to all_characters") ||
                            TextContains(text, "damage to all other characters"));
                    })
                    .ToDictionary(card => card.AssetId, card =>
                    {
                        int.TryParse(Regex.Match(card.Text, @"\d+").Value, out int amount);

                        return (amount, card.Type == CardType.SPELL);
                    });

            HarmfulDeathrattles =
                allStandardWithNonCollectibles
                    .Where(p =>
                    {
                        var text = p.Text ?? "";

                        return
                            (p.Deathrattle && p.Type == CardType.MINION) &&
                            ((TextContains(text, "deal") && TextContains(text, "damage") ||
                              TextContains(text, "destroy")) &&
                             (!TextContains(text, "hero") && !TextContains(text, "your") &&
                              !TextContains(text, "Friendly")));
                    })
                    .Select(p => p.AssetId)
                    .ToHashSet();
            #endregion

            //  private lists
            Taunts = Cards.AllStandard.Where(p => p.Taunt).ToArray();
            ClassTaunts.TryAdd(CardClass.NEUTRAL, Taunts.Where(p => p.Class == CardClass.NEUTRAL).ToArray());
            Beasts = Cards.AllStandard.Where(p => p.Race == Race.BEAST).ToArray();
            Dragons = Cards.AllStandard.Where(p => p.Race == Race.DRAGON).ToArray();
            Demons = Cards.AllStandard.Where(p => p.Race == Race.DEMON).ToArray();
            MageSpells = Cards.AllStandard.Where(p => p.Class == CardClass.MAGE && p.Type == CardType.SPELL && !p.IsQuest).ToArray();
            DKCards = allStandardWithNonCollectibles.Where(p => p.Id.StartsWith("ICC_314t")).ToArray();
            UngoroCards = Cards.All.Where(c => c.Set == CardSet.UNGORO && c.Collectible && !c.IsQuest).ToArray();
            #region Zombeasts
            var firstBeasts = new List<Card>();
            var secondBeasts = new List<Card>();
            var allBeasts = Cards.Standard[CardClass.HUNTER].Where(c => c.Race == Race.BEAST && c.Cost <= 5);
            foreach (Card card in allBeasts)
            {
                if (card.Power != null)
                    firstBeasts.Add(card);
                else
                    secondBeasts.Add(card);
            }

            var zombeasts = new List<Card>(firstBeasts.Count * secondBeasts.Count);

            foreach (var firstCard in firstBeasts)
            foreach (var secondCard in secondBeasts)
                zombeasts.Add(Card.CreateZombeastCard(in firstCard, in secondCard, false));
            Zombeasts = zombeasts;
            #endregion


            #region AllPlayables
            var allPlayableCards = allStandardWithNonCollectibles
                .Where(p =>
                    p.Type != CardType.HERO_POWER &&
                    (p.Type != CardType.HERO || p.Power != null) &&
                    !(p.Type == CardType.SPELL && (p.Id.EndsWith('a') || p.Id.EndsWith('b') || p.Id.EndsWith('c') ||
                                                   p.Id.EndsWith('d'))) &&
                    !p.Id.StartsWith("BOTA") &&
                    !p.Id.StartsWith("GILA") &&
                    !p.Id.StartsWith("ICCA") &&
                    !p.Id.StartsWith("BCON") &&
                    !p.Id.StartsWith("LOOTA") &&
                    (!p.Id.StartsWith("GAME") || p.Id == "GAME_005") &&
                    !p.Id.StartsWith("UNG_999t") &&
                    !p.Tags.ContainsKey(GameTag.TOPDECK) &&
                    !(p.Type == CardType.MINION && p.HideStat))
                .OrderBy(p => p.AssetId)
                .ToArray();

            AllPlayables = allPlayableCards
                .Select(p => p.AssetId)
                .ToArray();

            var targetTypes = new int[allPlayableCards.Length];
            var total = 0;
            for (int i = 0; i < allPlayableCards.Length; i++)
            {
                var card = allPlayableCards[i];
                bool musthaveTarget = false;
                bool targetIfAvailable = false;
                bool minionTarget = false;
                bool friendlyTarget = false;
                bool enemyTarget = false;
                bool heroTarget = false;
                int types = 5;

                foreach (var req in card.PlayRequirements)
                {
                    switch (req.Key)
                    {
                        case PlayReq.REQ_TARGET_TO_PLAY:
                            musthaveTarget = true;
                            break;
                        case PlayReq.REQ_TARGET_IF_AVAILABLE:
                        case PlayReq.REQ_NONSELF_TARGET:
                        case PlayReq.REQ_DRAG_TO_PLAY:
                        case PlayReq.REQ_TARGET_FOR_COMBO:
                        case PlayReq.REQ_TARGET_IF_AVAILABE_AND_ELEMENTAL_PLAYED_LAST_TURN:
                        case PlayReq.REQ_TARGET_IF_AVAILABLE_AND_DRAGON_IN_HAND:
                        case PlayReq.REQ_TARGET_IF_AVAILABLE_AND_MINIMUM_FRIENDLY_MINIONS:
                        case PlayReq.REQ_TARGET_IF_AVAILABLE_AND_MINIMUM_FRIENDLY_SECRETS:
                        case PlayReq.REQ_TARGET_IF_AVAILABLE_AND_NO_3_COST_CARD_IN_DECK:
                            targetIfAvailable = true;
                            break;
                        case PlayReq.REQ_MINION_TARGET:
                            minionTarget = true;
                            break;
                        case PlayReq.REQ_FRIENDLY_TARGET:
                            friendlyTarget = true;
                            break;
                        case PlayReq.REQ_ENEMY_TARGET:
                            enemyTarget = true;
                            break;
                        case PlayReq.REQ_HERO_TARGET:
                            heroTarget = true;
                            break;
                    }
                }

                if (musthaveTarget || targetIfAvailable)
                {
                    types--;
                    if (minionTarget)
                    {
                        types -= 2;
                        if (friendlyTarget || enemyTarget)
                            types--;
                    }
                    else if (heroTarget)
                        types -= 2;
                    else if (friendlyTarget || enemyTarget)
                        types -= 2;
                }
                else
                    types = 1;

                total += types;
                targetTypes[i] = types;
            }

            AllPlayablesCount = total;
            NumTargetTypesAvailable = targetTypes;
            #endregion

            //int minions = allStandardWithNonCollectibles.Count(c => c.Type == CardType.MINION);
        }

        static bool TextContains(string source, string str)
        {
            return _ci.CompareInfo.IndexOf(source, str, CompareOptions.IgnoreCase) >= 0;
        }

        public static bool CanRequireTarget(this Card c)
        {
            return
                c.RequiresTarget ||
                c.RequiresTargetForCombo ||
                c.RequiresTargetIfAvailable ||
                c.RequiresTargetIfAvailableAndDragonInHand ||
                c.RequiresTargetIfAvailableAndElementalPlayedLastTurn ||
                c.RequiresTargetIfAvailableAndMinimumFriendlyMinions ||
                c.RequiresTargetIfAvailableAndMinimumFriendlySecrets;
        }

        public static int CalculateAdditionalDamage(IPlayable entity)
        {
            switch (entity.Card.AssetId)
            {
                case 296:   //  Kill Command
                    return entity.Controller.BoardZone.Any(p => p.Race == Race.BEAST) ? 2 : 0;
                case 41126: //  Dispatch Kodo
                    return /*entity[GameTag.ATK] - 2;*/ ((Minion) entity).AttackDamage;
                case 391:   //  Perdition's blade
                    return entity.Controller.IsComboActive ? 1 : 0;
                case 45975: //	Spectral Pillager
                    return entity.Controller.NumCardsPlayedThisTurn;
                case 46996: //  Mulspark Eel
                    return entity.Controller.DeckZone.NoOddCostCards ? 0 : -2;
                default:
                    return 0;
            }
        }

        public static void GetRandomCard(IPlayable playable, Random rnd)
        {
            Card card;

            if (playable[GameTag.PUZZLE] == 1)
            {
	            var list = Cards.FormatTypeClassCards(playable.Game.FormatType)[playable.Controller.HeroClass];
	            card = list[rnd.Next(list.Count)];
            }
			else
			{
				
	            if (!playable.NativeTags.TryGetValue(GameTag.DISPLAYED_CREATOR, out int creatorId))
	                return;

	            if (!playable.Game.IdEntityDic.TryGetValue(creatorId, out var creator))
		            return;

	            var sourceCard = creator.Card;
	            if (sourceCard.Entourage.Length > 0)
	                card = Util.RandomElement(sourceCard.Entourage.Select(p => Cards.FromId(p)));

	            switch (sourceCard.AssetId)
	            {
	                case 41243:
	                    card = GetStonehillDefenderRandom(playable.Controller.BaseClass, rnd);
	                    break;
	                case 43183:     //  Build-A-Beast
	                    card = Zombeasts.Random(rnd);
	                    break;
	                case 41353:     //  Jeweled Macaw
	                case 38328:     //  Nerubian Spores (Infest)
	                    card = Beasts.Random(rnd);
	                    break;
	                case 42046:     //  Lyra the Sunshard
	                case 41875:     //  Chittering Tunneler
	                case 41496:     //  Primordial Glyph
	                {
	                    card = GetClassSpells(playable.Controller.Hero.Card.Class).Random(rnd);
	                        break;
	                    }
	                case 43414:     //	Lesser Ruby Spellstone
	                case 43412:     //	Ruby Spellstone
	                case 43411:		//	Greater Ruby Spellstone
	                case 39169:     //  Babbling Book
	                case 38418:     //  Cabalist's Tomb
	                case 41927:     //  Shimmering Tempest
	                    card = MageSpells.Random(rnd);
	                    break;
	                case 41177:     //  Curious Glimmerroot
	                    card = playable.Controller.Opponent.DeckCards.Random(rnd);
	                    break;
	                case 42439:     //  Bone Drake
	                    card = Dragons.Random(rnd);
	                    break;
	                case 39554:     //  Netherspite Historian
	                    card = Dragons.Where(p => p.Class == CardClass.NEUTRAL || p.Class == playable.Controller.BaseClass).ToArray().Random(rnd);
	                    break;
	                case 40940:     //  Kabal Trafficker
	                    card = Demons.Random(rnd);
	                    break;
	                case 45366:
	                case 42818:
	                    card = DKCards.Random(rnd);
	                    break;
	                case 40905:     //  Shaku, the Collector
	                case 39698:     //  Swashburglar
	                case 39026:     //  Undercity Huckster
	                    {
	                        card = Cards.AllStandard.Where(c => c.Class == playable.Controller.Opponent.BaseClass && c[GameTag.QUEST] == 0).ToArray().Random(rnd);
	                        break;
	                    }
	                //  TODO: need precise time when this card is created
	                case 42707:     //  Stitched Tracker
	                    card = playable.Controller.DeckCards.Where(p => p.Type == CardType.MINION).ToArray().Random(rnd);
	                    break;
	                case 41169:     //  Shadow Visions
	                    card = playable.Controller.DeckCards.Where(p => p.Type == CardType.SPELL).ToArray().Random(rnd);
	                    break;
	                case 41491:     //	Un'Goro Pack
	                    card = UngoroCards.Random(rnd);
	                    break;
	                //case 1099:    //  Mind Vision
	                //case 30:      //  Thoughtsteal
	                //case 42566:   //  Divour Mind
	                //case 40378:   //  Draknoid Operative
	                //case 41354:   //  Tol'vir Warden
	                //case 42646:   //  Kazakus
	                //case 1047:    //  Tracking ??
	                default:
	                    return;
	            }
			}

			if (card == null)
				return;

            //  TODO: Kazakus
            //  TODO: remove triggers and apply new enchantment (e.g. Bolvar) 

            playable.Controller.HandZone.Remove(playable);
            playable.Game.IdEntityDic.Remove(playable.Id);
            playable.Game.AuraUpdate();
            //var dic = new Dictionary<GameTag, int> { { GameTag.ENTITY_ID, playable.Id } };
            var result = Entity.FromCard(playable.Controller, card, playable.NativeTags
                , playable.Controller.HandZone, playable.Id);
            if (result.ChooseOne)
            {
                result.ChooseOnePlayables = new IPlayable[2];
                result.ChooseOnePlayables[0] = Entity.FromCard(playable.Controller,
                    Cards.FromId(result.Card.Id + "a"), null, playable.Controller.SetasideZone);
                result.ChooseOnePlayables[1] = Entity.FromCard(playable.Controller,
                    Cards.FromId(result.Card.Id + "b"), null, playable.Controller.SetasideZone);
            }
            playable.Game.AuraUpdate();
        }

        public static string PrintCategories(Predicate<Card> filter = null)
        {
            var sb = new StringBuilder();

            sb.AppendLine("###CardsHarmfulToTarget: ");
            foreach (var id in CardsHarmfulToTarget)
            {
                Card card = Cards.FromAssetId(id);
                if (filter != null && !filter(card)) continue;
                sb.AppendLine($"{card.Name}");
            }
            sb.AppendLine();

            sb.AppendLine("###BeneficialToTarget: ");
            foreach (var id in BeneficialToTarget)
            {
                Card card = Cards.FromAssetId(id);
                if (filter != null && !filter(card)) continue;
                sb.AppendLine($"{card.Name}");
            }

            return sb.ToString();
        }

        public static Card GetRandomMageSpell(Random rnd)
        {
	        return MageSpells.Random(rnd);
        }
    }

    public partial class CardCategory
    {
        private static readonly Card[] Taunts;
        private static readonly Card[] Beasts;
        private static readonly Card[] Dragons;
        private static readonly Card[] Demons;
        private static readonly Card[] MageSpells;
        private static readonly Card[] DKCards;
        private static readonly List<Card> Zombeasts;
        private static readonly ConcurrentDictionary<CardClass, Card[]> ClassSpells = new ConcurrentDictionary<CardClass, Card[]>();
        private static readonly ConcurrentDictionary<CardClass, Card[]> ClassTaunts = new ConcurrentDictionary<CardClass, Card[]>();
        private static readonly Card[] UngoroCards;

        private static Card[] GetClassSpells(CardClass cardClass)
        {
            if (ClassSpells.TryGetValue(cardClass, out Card[] cards))
                return cards;
            Card[] cardList = Cards.AllStandard.Where(p => p.Class == cardClass && p.Type == CardType.SPELL && !p.IsQuest).ToArray();

            ClassSpells.TryAdd(cardClass, cardList);
            return cardList;
        }

        private static Card GetStonehillDefenderRandom(CardClass cc, Random rnd)
        {
            if (rnd.Next(5) == 0)
                return ClassTaunts[CardClass.NEUTRAL].Random(rnd);

            if (!ClassTaunts.TryGetValue(cc, out Card[] classTaunt))
            {
                classTaunt = Taunts.Where(p => p.Class == cc).ToArray();

                ClassTaunts.TryAdd(cc, classTaunt);
            }

            return classTaunt.Length == 0 ? ClassTaunts[CardClass.NEUTRAL].Random(rnd) : classTaunt.Random(rnd);
        }
    }

    public partial class CardCategory
    {
        public static int[] AllPlayables;
        public static int[] NumTargetTypesAvailable;

        public static readonly int AllPlayablesCount;
    }
}
