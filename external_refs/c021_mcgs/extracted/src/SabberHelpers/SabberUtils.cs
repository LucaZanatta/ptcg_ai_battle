using System;
using System.Linq;
using System.Text;
using SabberStoneCoreAi.MCGS.Heuristics;
using SabberStoneCore.Model;
using SabberStoneCore.Model.Entities;
using SabberStoneCore.Tasks.PlayerTasks;

namespace SabberStoneCoreAi.MCGS.SabberHelper
{
    public static partial class SabberUtils
    {
	    internal static void Determinize(Game game, Random rnd, bool all = false)
        {
            if (all)
                game.CurrentPlayer.DeckZone.Shuffle();

            Action auraUpdate = game.AuraUpdate;

            var hand = game.CurrentOpponent.HandZone;
            var deck = game.CurrentOpponent.DeckZone;
            var n = hand.Count;
            for (var i = n; i > 0;)
            {
                var card = hand[--i];

                //  TODO: Arcanologist, T. Warden
                //  TODO: preserve enchants in hand & add cases
                if (card.Id > 67)
                {
                    CardCategory.GetRandomCard(card, rnd);
                }
                else
                {
                    //deck.MoveTo(hand.Remove(card), deck.Count);
                    //hand.MoveTo(deck.Remove(deck.Random), hand.Count);
                    deck.Add(hand.Remove(card));
                    //game.AuraUpdate();
                    auraUpdate();
                    hand.Add(deck.Remove(deck[rnd.Next(deck.Count)]));
                    //game.AuraUpdate();
                    auraUpdate();
                }
            }
            deck.Shuffle();

            //game.AuraUpdate();
        }

	    public static bool HasSource(this PlayerTask action)
        {
            return action.PlayerTaskType == PlayerTaskType.PLAY_CARD || action.PlayerTaskType == PlayerTaskType.MINION_ATTACK;
        }

        public static bool HasChoice(this Game game)
        {
            return game.CurrentPlayer.Choice != null;
        }

        internal static bool CanOpponentBeAttacked(this Game game)
        {
            return !game.CurrentOpponent.Hero.IsImmune && !game.CurrentOpponent.Hero.HasStealth;
        }

        //  TODO: exclude external auras (e.g. Stormwind Champion)
        public static bool CanBeSilenced(this Minion m)
        {
            return m.HasTaunt || m.HasDeathrattle || m.HasDivineShield || m.HasWindfury || m.HasWindfury || m.IsEnraged ||
                   m.IsFrozen || m.Poisonous
            //|| m.Enchants.Any() || m.Enchantments.Any(e => e.Activation == EnchantmentActivation.BOARD_ZONE);
            || m.OngoingEffect != null;
        }

        public static bool IsDistinguishable(this Minion p)
        {
            //return (p.IsDeathrattle || (p.Enchantments != null && p.Enchantments.Any(e => e.Activation == EnchantmentActivation.BOARD_ZONE)));
            return p.HasDeathrattle || p.OngoingEffect != null || p.ActivatedTrigger != null;
        }

        #region printers
        public static string ActionPrint(PlayerTask a)
        {
            var name = a.Controller.Name;

            switch (a.PlayerTaskType)
            {
                case PlayerTaskType.CHOOSE:
                    var c = a as ChooseTask;
                    return $"[{name}] chose {c.Game.IdEntityDic[c.Choices.First()]}";
                case PlayerTaskType.END_TURN:
                    return $"[{name}] ended his turn.";
                case PlayerTaskType.HERO_ATTACK:
                    return $"[{name}]'s {a.Controller.Hero} attacked {a.Target}";
                case PlayerTaskType.HERO_POWER:
                    return $"[{name}] used {a.Controller.Hero.HeroPower}" + $"{(a.Target != null ? $" to {a.Target}" : "")}" + $"{(a.Controller.Hero.HeroPower.ChooseOne ? $" with SubOption: {a.ChooseOne}" : "")}";
                case PlayerTaskType.MINION_ATTACK:
                    return $"[{name}]'s {a.Source} attacked {a.Target}";
                case PlayerTaskType.PLAY_CARD:
                    if (a.Source is Minion)
                        return $"[{name}] played {a.Source} to Position {((PlayCardTask)a).ZonePosition}" + $"{(a.Target != null ? $" and targeted {a.Target}" : "")}" + $" {(a.Source.Card.ChooseOne ? $" with SubOption: {a.ChooseOne}" : "")}";
                    else
                        return $"[{name}] played {a.Source}" + $"{(a.Target != null ? $" to {a.Target}" : "")}" + $"{(a.Source.Card.ChooseOne ? $" with SubOption: {a.ChooseOne}" : "")}";
                default:
                    return "";
            }
        }

        public static string PrintGame(Game game)
        {
            var current = game.CurrentPlayer;
            var opponent = game.CurrentOpponent;
            var sb = new StringBuilder();
            sb.AppendLine("");
            sb.AppendLine($"ROUND {(game.Turn + 1) / 2} - {current.Name}\n");
            //sb.AppendLine($"Hero[P1]: {game.Player1.Hero.Health + game.Player1.Hero.Armor} / Hero[P2]: {game.Player2.Hero.Health + game.Player2.Hero.Armor}");
            sb.AppendLine($"[Op Hero: {opponent.Hero.Health}{(opponent.Hero.Armor == 0 ? "" : $" + {opponent.Hero.Armor}")}][{game.CurrentOpponent.Hero}]");
            if (opponent.Hero.Weapon != null)
            {
                sb.AppendLine($"[Op Weapon: {opponent.Hero.Weapon}({opponent.Hero.Weapon.AttackDamage}/{opponent.Hero.Weapon.Durability})]");
            }

            if (opponent.SecretZone.Count > 0 || opponent.SecretZone.Quest != null)
            {
                sb.Append($"[Op Secrets: ");
                opponent.SecretZone.ToList().ForEach(p =>
                {
                    var s = p;
                    if (s.IsQuest)
                        sb.Append($"{s}({s.QuestProgress})");
                    else
                        sb.Append(s);
                });
                sb.Append("]\n");
            }

            //if (opponent.SecretZone.Quest != null)
            //{
            // sb.Append("[Op Quest: ");

            //}
            sb.Append("[Op Board: ");
            opponent.BoardZone.ToList().ForEach(m =>
            {
                var str = new StringBuilder();
                str.Append($"({m.AttackDamage}/{m.Health})");
                str.Append(m);
                str.Append(" | ");
                sb.Append(str.ToString());
            });
            sb.Append("]\n");
            sb.Append("[Board: ");
            current.BoardZone.ToList().ForEach(m =>
            {
                var str = new StringBuilder();
                str.Append($"({m.AttackDamage}/{m.Health})");
                str.Append(m);
                str.Append(" | ");
                sb.Append(str.ToString());
            });
            sb.Append("]\n");
            sb.AppendLine($"[Hero: {current.Hero.Health}{(current.Hero.Armor == 0 ? "" : $" + {current.Hero.Armor}")}][{game.CurrentPlayer.Hero}][Power: ({current.Hero.HeroPower.Cost}){current.Hero.HeroPower}]");
            if (current.Hero.Weapon != null)
            {
                sb.AppendLine($"[Weapon: {current.Hero.Weapon}({current.Hero.Weapon.AttackDamage}/{current.Hero.Weapon.Durability})]");
            }
            if (current.SecretZone.Count > 0 || current.SecretZone.Quest != null)
            {
                sb.Append($"[Secrets: ");
                current.SecretZone.ToList().ForEach(s =>
                {
                    if (s.IsQuest)
                        sb.Append($"{s}({s.QuestProgress})");
                    else
                        sb.Append(s);
                });
                sb.Append("]\n");
            }
            sb.Append("[Hand: ");
            current.HandZone.ToList().ForEach(p =>
            {
                sb.Append($"({p.Cost})");
                sb.Append(p);
            });
            sb.Append("]\n");
            sb.AppendLine($"[Mana:{current.RemainingMana}/{current.OverloadOwed}/{current.BaseMana}][{current.OverloadLocked}]");

            return sb.ToString();
        }

        public static void ShowLog(Game game, LogLevel level)
        {
            while (game.Logs.Count > 0)
            {
                var logEntry = game.Logs.Dequeue();
                if (logEntry.Level <= level)
                {
                    var foreground = ConsoleColor.White;
                    switch (logEntry.Level)
                    {
                        case LogLevel.DUMP:
                            foreground = ConsoleColor.DarkCyan;
                            break;
                        case LogLevel.ERROR:
                            foreground = ConsoleColor.Red;
                            break;
                        case LogLevel.WARNING:
                            foreground = ConsoleColor.DarkRed;
                            break;
                        case LogLevel.INFO:
                            foreground = logEntry.Location.Equals("Game") ? ConsoleColor.Yellow :
                                         logEntry.Location.StartsWith("Quest") ? ConsoleColor.Cyan :
                                         ConsoleColor.Green;
                            break;
                        case LogLevel.VERBOSE:
                            foreground = ConsoleColor.DarkGreen;
                            break;
                        case LogLevel.DEBUG:
                            foreground = ConsoleColor.DarkGray;
                            break;
                        default:
                            throw new ArgumentOutOfRangeException();
                    }

                    Console.ForegroundColor = foreground;

                    Console.WriteLine(
                        $"{logEntry.TimeStamp} - {logEntry.Level} [{logEntry.BlockType}] - {logEntry.Location}: {logEntry.Text}");
                }
            }
            Console.ResetColor();
        }
        #endregion
    }
}
