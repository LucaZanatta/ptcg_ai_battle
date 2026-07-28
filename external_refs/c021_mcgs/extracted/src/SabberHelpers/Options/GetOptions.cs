using System;
using SabberStoneCore.Enums;
using SabberStoneCore.Model.Entities;
using SabberStoneCoreAi.MCGS.SabberHelper.Option;
using SabberStoneCore.Loader;
using SabberStoneCore.Model;

namespace SabberStoneCoreAi.MCGS.SabberHelper
{
    public static partial class SabberUtils
    {
        // [0] End Turn
        // [1] Play Card
        // [2] Hero Power
        // [3] Attack
        public static Options GetOptions(this Controller controller, Options options = null)
        {
            //	TODO: Check if it's the controller's turn


            if (options != null)
                options.Reset(in controller);
            else
                options = new Options(in controller);

            // Skip	EndTurnTask

            #region PlayCardTasks
            Character[] allTargets = null;
            Minion[] friendlyMinions = null;
            Minion[] enemyMinions = null;
            Minion[] allMinions = null;
            Character[] allFriendly = null;
            Character[] allEnemies = null;

            ReadOnlySpan<Minion> boardSpan = controller.BoardZone.GetSpan();
            ReadOnlySpan<IPlayable> handSpan = controller.HandZone.GetSpan();
            int mana = controller.RemainingMana;
            int zonePosRange = boardSpan.Length;
            bool isBoardFull = zonePosRange == 7;

            // Create a set to consider only distinct play sources
            for (int i = 0; i < handSpan.Length; i++)
            {
                if (!handSpan[i].ChooseOne || controller.ChooseBoth)
                    GetPlayCardTasks(handSpan[i]);
                else
                {
                    IPlayable[] playables = handSpan[i].ChooseOnePlayables;
                    for (int j = 1; j < 3; j++)
                        GetPlayCardTasks(handSpan[i], playables[j - 1], j);
                }
            }
            #endregion

            #region HeroPowerTask
            HeroPower power = controller.Hero.HeroPower;
            Card heroPowerCard = power.Card;
            if (!power.IsExhausted && mana >= power.Cost && !controller.HeroPowerDisabled && !heroPowerCard.HideStat)
            {
                if (power.ChooseOne)
                {
                    if (controller.ChooseBoth)
                        options.HeroPowerOption = new HeroPowerOption(false);
                    else
                        options.HeroPowerOption = new HeroPowerOption(true);
                }
                else
                {
                    if (heroPowerCard.IsPlayableByCardReq(in controller))
                    {
                        Character[] targets = GetTargets(heroPowerCard);
                        if (targets != null)
                        {
                            if (targets.Length != 0)
                                options.HeroPowerOption = new HeroPowerOption(targets);
                        }
                        else
                            options.HeroPowerOption = new HeroPowerOption(false);
                    }

                }
            }
            #endregion

            #region MinionAttackTasks
            Minion[] attackTargets = null;
            bool isOpHeroValidAttackTarget = false;
            //List<AttackOption> attackOptions = new List<AttackOption>(boardSpan.Length);
            //options.AttackOptions = attackOptions;
            for (int j = 0; j < boardSpan.Length; j++)
            {
                Minion minion = boardSpan[j];

                if (minion.IsExhausted && (!minion.HasCharge || minion.NumAttacksThisTurn != 0))
                    continue;
                if (minion.IsFrozen || minion.AttackDamage == 0 || minion.CantAttack)
                    continue;

                GenerateAttackTargets();

                bool heroFlag =
                    isOpHeroValidAttackTarget && !(minion.AttackableByRush || minion.CantAttackHeroes);

                if (attackTargets.Length > 0 || heroFlag)
                    options.AddAttackOption(new AttackOption(minion, attackTargets, heroFlag));
            }

            #endregion

            #region HeroAttackTasks
            Hero hero = controller.Hero;

            if (!hero.IsExhausted && hero.AttackDamage > 0 && !hero.IsFrozen)
            {
                GenerateAttackTargets();

                options.AddAttackOption(new AttackOption(attackTargets,
                    isOpHeroValidAttackTarget && !hero.CantAttackHeroes));
            }
            #endregion

            return options;

            #region local functions
            void GetPlayCardTasks(IPlayable playable, IPlayable chooseOnePlayable = null, int subOption = 0)
            {
                // TODO: spell_cost_health

                Card card = chooseOnePlayable?.Card ?? playable.Card;


                if (playable.Cost > mana || card.HideStat)
                    return;

                switch (card.Type)
                {
                    case CardType.MINION when isBoardFull:
                        return;
                    case CardType.SPELL when card.IsSecret:
                    {
                        if (controller.SecretZone.IsFull) // REQ_SECRET_CAP
                            return;
                        if (controller.SecretZone.Any(p => p.Card.AssetId == card.AssetId)) // REQ_UNIQUE_SECRET
                            return;
                        break;
                    }
                    case CardType.SPELL when card.IsQuest && controller.SecretZone.Quest != null:
                        return;
                }


                if (!card.IsPlayableByCardReq(in controller))
                    return;

                GetPlayCardTaskInternal(card, playable, subOption);
            }

            void GetPlayCardTaskInternal(Card card, IPlayable playable, int subOption)
            {
	            Character[] targets = GetTargets(card);

                // Card doesn't require any targets
                if (targets == null)
                {
                    options.AddPlayCardOption(playable is Minion
                        ? new PlayCardOption(playable, null, zonePosRange, subOption)
                        : new PlayCardOption(playable, subOption));
                }
                else
                {
                    if (targets.Length == 0)
                    {
                        if (card.MustHaveTargetToPlay)
                        {
	                        return;
                        }

                        options.AddPlayCardOption(playable is Minion
                            ? new PlayCardOption(playable, null, zonePosRange, subOption)
                            : new PlayCardOption(playable, subOption));
                    }
                    else
                    {
                        options.AddPlayCardOption(playable is Minion
                            ? new PlayCardOption(playable, targets, zonePosRange, subOption)
                            : new PlayCardOption(playable, targets, subOption));
                    }
                }
            }

            // Returns null if targeting is not required
            // Returns 0 Array if there is no available target
            Character[] GetTargets(Card card)
            {
                // Check it needs additional validation
                if (!card.TargetingAvailabilityPredicate?.Invoke(controller) ?? false)
                    return null;

                Character[] targets;

                switch (card.TargetingType)
                {
                    case TargetingType.None:
                        return null;
                    case TargetingType.All:
                        if (allTargets == null)
                        {
                            if (controller.Opponent.Hero.HasStealth)
                            {
                                allTargets = new Character[GetFriendlyMinions().Length + GetEnemyMinions().Length + 1];
                                allTargets[0] = controller.Hero;
                                Array.Copy(GetAllMinions(), 0, allTargets, 1, allMinions.Length);
                            }
                            else
                            {
                                allTargets = new Character[GetFriendlyMinions().Length + GetEnemyMinions().Length + 2];
                                allTargets[0] = controller.Hero;
                                allTargets[1] = controller.Opponent.Hero;
                                Array.Copy(GetAllMinions(), 0, allTargets, 2, allMinions.Length);
                            }
                        }

                        targets = allTargets;
                        break;
                    case TargetingType.FriendlyCharacters:
                        if (allFriendly == null)
                        {
                            allFriendly = new Character[GetFriendlyMinions().Length + 1];
                            allFriendly[0] = controller.Hero;
                            Array.Copy(friendlyMinions, 0, allFriendly, 1, friendlyMinions.Length);
                        }

                        targets = allFriendly;
                        break;
                    case TargetingType.EnemyCharacters:
                        if (allEnemies == null)
                        {
                            if (!controller.Opponent.Hero.HasStealth)
                            {
                                allEnemies = new Character[GetEnemyMinions().Length + 1];
                                allEnemies[0] = controller.Opponent.Hero;
                                Array.Copy(enemyMinions, 0, allEnemies, 1, enemyMinions.Length);
                            }
                            else
                                allEnemies = GetEnemyMinions();
                        }

                        targets = allEnemies;
                        break;
                    case TargetingType.AllMinions:
                        targets = GetAllMinions();
                        break;
                    case TargetingType.FriendlyMinions:
                        targets = GetFriendlyMinions();
                        break;
                    case TargetingType.EnemyMinions:
                        targets = GetEnemyMinions();
                        break;
                    case TargetingType.Heroes:
                        targets = !controller.Opponent.Hero.HasStealth
                            ? new[] {controller.Hero, controller.Opponent.Hero}
                            : new[] {controller.Hero};
                        break;
                    default:
                        throw new ArgumentOutOfRangeException();
                }

                // Filtering for target_if_available
                TargetingPredicate p = card.TargetingPredicate;
                if (p != null)
                {
                    if (card.Type == CardType.SPELL || card.Type == CardType.HERO_POWER)
                    {
                        Character[] buffer = new Character[targets.Length];
                        int i = 0;
                        for (int j = 0; j < targets.Length; ++j)
                        {
                            if (!p(targets[j]) || targets[j].CantBeTargetedBySpells) continue;
                            buffer[i] = targets[j];
                            i++;
                        }

                        if (i != targets.Length)
                        {
                            Character[] result = new Character[i];
                            Array.Copy(buffer, result, i);
                            return result;
                        }

                        return buffer;
                    }
                    else
                    {
                        if (!card.TargetingAvailabilityPredicate?.Invoke(controller) ?? false)
                            return null;

                        Character[] buffer = new Character[targets.Length];
                        int i = 0;
                        for (int j = 0; j < targets.Length; ++j)
                        {
                            if (!p(targets[j])) continue;
                            buffer[i] = targets[j];
                            i++;
                        }

                        if (i != targets.Length)
                        {
                            Character[] result = new Character[i];
                            Array.Copy(buffer, result, i);
                            return result;
                        }

                        return buffer;
                    }
                }
                else if (card.Type == CardType.SPELL || card.Type == CardType.HERO_POWER)
                {
                    Character[] buffer = new Character[targets.Length];
                    int i = 0;
                    for (int j = 0; j < targets.Length; ++j)
                    {
                        if (targets[j].CantBeTargetedBySpells) continue;
                        buffer[i] = targets[j];
                        i++;
                    }

                    if (i != targets.Length)
                    {
                        Character[] result = new Character[i];
                        Array.Copy(buffer, result, i);
                        return result;
                    }

                    return buffer;
                }

                return targets;

                Minion[] GetFriendlyMinions()
                {
                    return friendlyMinions ?? (friendlyMinions = controller.BoardZone.GetAll());
                }

                Minion[] GetAllMinions()
                {
                    if (allMinions != null)
                        return allMinions;

                    allMinions = new Minion[GetEnemyMinions().Length + GetFriendlyMinions().Length];
                    Array.Copy(enemyMinions, allMinions, enemyMinions.Length);
                    Array.Copy(friendlyMinions, 0, allMinions, enemyMinions.Length, friendlyMinions.Length);

                    return allMinions;
                }
            }

            void GenerateAttackTargets()
            {
                if (attackTargets != null) return;

                Minion[] eMinions = GetEnemyMinions();
                Minion[] taunts = null;
                int tCount = 0;
                for (int i = 0; i < eMinions.Length; i++)
                    if (eMinions[i].HasTaunt)
                    {
                        if (taunts == null)
                            taunts = new Minion[eMinions.Length];
                        taunts[tCount] = eMinions[i];
                        tCount++;
                    }

                if (tCount > 0)
                {
                    var targets = new Minion[tCount];
                    Array.Copy(taunts, targets, tCount);
                    attackTargets = targets;
                    isOpHeroValidAttackTarget = false;  // some brawls allow taunt heros and this should be fixed
                    return;
                }
                attackTargets = eMinions;

                isOpHeroValidAttackTarget =
                    !controller.Opponent.Hero.IsImmune && !controller.Opponent.Hero.HasStealth;
            }

            Minion[] GetEnemyMinions()
            {
                return enemyMinions ?? (enemyMinions = controller.Opponent.BoardZone.GetAll(p => !p.HasStealth && !p.IsImmune));
            }
            #endregion
        }
    }
}
