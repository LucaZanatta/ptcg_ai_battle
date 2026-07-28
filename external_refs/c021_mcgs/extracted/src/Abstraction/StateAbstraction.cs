using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using SabberStoneCoreAi.MCGS.Heuristics;
using SabberStoneCoreAi.MCGS.SabberHelper;
using SabberStoneCore.Enums;
using SabberStoneCore.Model;
using SabberStoneCore.Model.Entities;

namespace SabberStoneCoreAi.MCGS.Abstraction
{
    public class StateAbstraction : IEquatable<StateAbstraction>
    {
        public override int GetHashCode()
        {
            //if (_hashCode == 0)
            //    _hashCode = HashCode.Combine(
            //        Utils.IntArrayComparer.ArrayHashCode(_ids),
            //        Utils.IntArrayComparer.ArrayHashCode(_boards),
            //        _opDeckCount,
            //        Utils.IntArrayComparer.ArrayHashCode(_deck),
            //        _actionHashCode);
            if (_hashCode == 0)
            {
	            int hash = Utils.IntArrayComparer.ArrayHashCode(_ids);
	            hash = unchecked(hash * 17 + Utils.IntArrayComparer.ArrayHashCode(_boards));
	            hash = unchecked(hash * 17 + _opDeckCount);
	            hash = unchecked(hash * 17 + Utils.IntArrayComparer.ArrayHashCode(_deck));
	            hash = unchecked(hash * 17 + _actionHashCode);
				_hashCode = hash;
            }

            return _hashCode;
        }

        private int DebugHashCode => GetHashCode();

        private const int HeroLength = 17;
        private const int ControllerLength = 4;
        private const int SecretLength = 6;

        private static readonly Utils.IntArrayComparer IntArrayComparer = new Utils.IntArrayComparer();

        private int[][][] _ids;
        private int[][][] _boards;
        private int[] _deck;
        //private readonly int[] _opDeck;
        private int _opDeckCount;
        private readonly int _actionHashCode;

        public readonly bool Simple;
        public bool Complete;
        public readonly bool ContainsDeck;
        public readonly Dictionary<int, int[]> HashDic = new Dictionary<int, int[]>();
        private int[] _opHandIds;

        private int[][] ChoiceInfo => _ids[0];
        private int[][] Hand
        {
            get => _ids[1];
            set => _ids[1] = value;
        }
        private int[][] OpHand
        {
            get => _ids[4];
            set => _ids[4] = value;
        }
        private int[][] Board => _boards[0];
        private int[][] OpBoard => _boards[1];
        private int[] Controller
        {
            get => _ids[2][0];
            set => _ids[2][0] = value;
        }

        private int[] Hero => _ids[2][1];

        private int[] OpSecrets => _ids[3][2];

        // Construct a Chance node abstraction.
        public StateAbstraction(StateAbstraction abstraction, ActionAbstraction chanceAction)
        {
            Simple = abstraction.Simple;
            Complete = abstraction.Complete;
            ContainsDeck = abstraction.ContainsDeck;

            _ids = abstraction._ids;
            _boards = abstraction._boards;

            //_board = abstraction._board;
            //_opBoard = abstraction._opBoard;

            _opDeckCount = abstraction._opDeckCount;
            _deck = abstraction._deck;

            _actionHashCode = chanceAction.GetHashCode();

            HashDic = abstraction.HashDic;

            // Discard private information for end turn chance nodes
            if (chanceAction.IsEndTurnAction)
            {
                var newIds = new int[_ids.Length][][];
                Array.Copy(_ids, newIds, newIds.Length);
                newIds[1] = new[] { new[] { Hand.Length } };
                if (Complete)
                    newIds[4] = new[] { new[] { OpHand.Length } };
                newIds[2] = new[] { new[] { Controller[2] } };    // Overload Locked
                _ids = newIds;
            }
        }

        // Construct a Decision node abstraction.
        internal StateAbstraction(Game game, bool simple = false, bool complete = false, bool containsDeck = false)
        {
            //_game = game.Clone();
            Simple = simple;
            Complete = complete;
            ContainsDeck = containsDeck;
            ReflectGame(game, simple, complete, containsDeck);
        }

        /// <summary>
        /// Remove all hidden information from the perfect state abstraction.
        /// </summary>
        /// <param name="perfect"></param>
        /// <param name="current"></param>
        private StateAbstraction(StateAbstraction perfect, bool current)
        {
            if (!perfect.Complete)
             throw new Exception("Can't extract incomplete from incomplete abstraction");

            int[][][] perfectIds = perfect._ids;

            int[][][] ids = new int[perfectIds.Length][][];
            
            // Get choice information
            if (perfect._ids[0] != null)
                ids[0] = new[] {new[] {perfectIds[0][0].Length}};

            for (int i = 1; i < ids.Length; i++)
                ids[i] = perfectIds[i];

            if (current)
            {
                // Remove opponent hand information
                ids[4] = new[] {new[] {perfectIds[4].Length}};
            }
            else
            {
                // Remove current hand information
                ids[1] = new[] {new[] {perfectIds[1].Length}};    
            }

            _ids = ids;
            _boards = perfect._boards;

            //_board = perfect._board;
            //_opBoard = perfect._opBoard;

            _opDeckCount = perfect._opDeckCount;
            _deck = perfect._deck;

            _actionHashCode = perfect._actionHashCode;

            HashDic = perfect.HashDic;
        }

        public StateAbstraction CreateInformationPoV(bool current = false)
        {
            return new StateAbstraction(this, current);
        }
        public void AddDeckAbstraction(in Controller currentPlayer)
        {
            var deckspan = currentPlayer.DeckZone.GetSpan();
            var deck = new int[deckspan.Length];
            for (int i = 0; i < deckspan.Length; i++)
                deck[i] = deckspan[i].Card.AssetId;
            Array.Sort(deck);
            _deck = deck;
        }

        public void MakeComplete(in Game game)
        {
            Controller opponent = game.CurrentOpponent;
            {
                var secretZone = opponent.SecretZone.GetSpan();
                for (var i = 0; i < secretZone.Length; i++)
                    OpSecrets[i] = secretZone[i].Card.AssetId;
                OpSecrets[5] = opponent.SecretZone.Quest?.Card.AssetId ?? 0;
            }
            OpHand = ReflectHand(opponent, Simple, HashDic);
            Complete = true;
        }

        //  TODO: Simplify OOP => handle subtle situations (e.g. Redemption, Escape Kodo ...)
        private void ReflectGame(Game game, bool simple = false, bool complete = false, bool containsDeck = false)
        {
            Controller current = game.CurrentPlayer;
            Controller opponent = game.CurrentOpponent;
            Dictionary<int, int[]> hashDic = HashDic;

            int[][] choiceInfo = ReflectChoices(current);
            int[][] board = ReflectBoard(current, simple, hashDic);
            int[][] opBoard = ReflectBoard(opponent, simple, hashDic);
            int[][] hand = ReflectHand(current, simple, hashDic);
            int[] hero = ReflectHero(current.Hero);

            // Controller
            int[] controller = new int[ControllerLength];
            controller[0] = current.BaseMana;
            controller[1] = current.RemainingMana;
            controller[2] = current.OverloadLocked;
            controller[3] = current.OverloadOwed;

            // Secrets
            int[] secrets = new int[SecretLength];
            ReadOnlySpan<Spell> secretZone = current.SecretZone.GetSpan();
            for (var i = 0; i < secretZone.Length; i++)
                secrets[i] = secretZone[i].Card.AssetId;
            secrets[5] = current.SecretZone.Quest?.Card.AssetId ?? 0;

            // Op Controller
            int[] opController = new int[ControllerLength];
            opController[0] = opponent.BaseMana;
            //if (complete) opController[1] = opponent.RemainingMana; Is op's remaining mana even needed?
            opController[2] = opponent.OverloadLocked;
            opController[3] = opponent.OverloadOwed;
            var opHero = ReflectHero(opponent.Hero);

            // Op secrets
            var opSecrets = new int[SecretLength];
            if (complete)
            {
                secretZone = opponent.SecretZone.GetSpan();
                for (var i = 0; i < secretZone.Length; i++)
                    opSecrets[i] = secretZone[i].Card.AssetId;
                opSecrets[5] = opponent.SecretZone.Quest?.Card.AssetId ?? 0;
            }
            else
            {
                opSecrets[0] = opponent.SecretZone.Count;
                opSecrets[1] = opponent.SecretZone.Quest?.Card.AssetId ?? 0;
            }

            // Op hand
            //  TODO: utilise opponentmodel
            int[][] opHand;
            if (complete)
                opHand = ReflectHand(opponent, simple, hashDic);
            else
            {
                opHand = new int[1][];
                opHand[0] = new[] {opponent.HandZone.Count};
            }

            int[][] playerInfo = {controller, hero, secrets};
            int[][] opPlayerInfo = {opController, opHero, opSecrets};

            _ids = new[] {choiceInfo, hand, playerInfo, opPlayerInfo, opHand /*, _graveyardInfo*/};
            _boards = new[] {board, opBoard};

            if (containsDeck)
            {
                if (!complete)
                    AddDeckAbstraction(in current);
                else
                    AddDeckAbstraction(in opponent);
            }

            _opDeckCount = opponent.DeckZone.Count;

            if (!hashDic.ContainsKey(current.Hero.Id))
                hashDic.Add(current.Hero.Id, PlayableHash(current.Hero, simple));
            if (!hashDic.ContainsKey(opponent.Hero.Id))
                hashDic.Add(opponent.Hero.Id, PlayableHash(opponent.Hero, simple));
        }

        private static int[][] ReflectChoices(Controller c)
        {
            if (c.Choice == null)
                return null;

            var dict = c.Game.IdEntityDic;

            // AssetIds of the current choices
            int[] choices = c.Choice.Choices.Select(p => dict[p].Card.AssetId).OrderBy(p => p)
                .ToArray();


			int[] choiceAncillaries = new int[4 + (c.Choice.TargetIds?.Count ?? 0)];

			choiceAncillaries[0] =
				c.Choice.LastChoice != 0 ? dict[c.Choice.LastChoice].Card.AssetId : 0;

			if (c.Choice.ChoiceQueue.Count > 0)
			{
				var nextChoice = c.Choice.ChoiceQueue.Peek().Choices
					.Select(i => dict[i].Card.AssetId).OrderBy(i => i).ToArray();
				Array.Copy(nextChoice, 0, choiceAncillaries, 1, 3);
			}

			if (c.Choice.TargetIds?.Count > 0)
			{
				var targets = c.Choice.TargetIds.Select(i => dict[i].Card.AssetId).OrderBy(i => i)
					.ToArray();
				Array.Copy(targets, 0, choiceAncillaries, 4, targets.Length);
			}

			//var list = new List<int>();
			//int buf = c.Choice.LastChoice;
			//if (buf != 0) list.Add(buf);
			//if (c.Choice.NextChoice != null)
			//    list.AddRange(c.Choice.NextChoice.Choices
			//        .Select(i => dict[i].Card.AssetId)
			//        .OrderBy(i => i));
			//int[] choiceAncillaries = list.ToArray();

			return new[] {choices, choiceAncillaries};
        }

        private static int[][] ReflectHand(Controller c, bool simple, Dictionary<int, int[]> hashDic)
        {
            ReadOnlySpan<IPlayable> hand = c.HandZone.GetSpan();
            var buffer = new int[hand.Length][];

            for (int i = 0; i < buffer.Length; i++)
            {
                var hash = PlayableHash(hand[i], simple);
                int id = hand[i].Id;

                hashDic.Add(id, hash);

                buffer[i] = hash;
            }

            Array.Sort(buffer, IntArrayComparer);
            return buffer;
        }

        private static int[][] ReflectBoard(Controller c, bool simple, Dictionary<int, int[]> hashDic)
        {
            var board = c.BoardZone;
            var buffer = new int[7][];
            bool considerPosition = false;

            for (int i = 0; i < board.Count; i++)
            {
                Minion m = board[i];
                var hash = PlayableHash(m, simple);
                hashDic.Add(m.Id, hash);
                buffer[i] = hash; 
                if (CardCategory.AdjacentEffectMinions.Contains(m.Card.AssetId) && m.OngoingEffect != null)
                    considerPosition = true;
            }

            //for (int i = board.Count; i < board.MaxSize; i++)
            //	buffer[i] = new int[0];

            if (simple && !considerPosition)
                Array.Sort(buffer, IntArrayComparer);

            return buffer;
        }

        private static int[] ReflectHero(Hero hero)
        {
            int[] heroArray = new int[HeroLength];

            HeroPower power = hero.HeroPower;
            heroArray[0] = (int)hero.Card.Class;
            heroArray[1] = hero.Health;
            heroArray[2] = hero.Armor;
            heroArray[3] = hero.AttackDamage;
            heroArray[4] = hero.IsExhausted ? 1 : 0;
            heroArray[5] = hero.HasStealth ? 1 : 0;
            heroArray[6] = hero.IsImmune ? 1 : 0;
            heroArray[7] = hero.Fatigue;
            heroArray[8] = power.Card.AssetId;
            heroArray[9] = power.Cost;
            heroArray[10] = power.IsExhausted ? 0 : 1;

            if (hero.Weapon == null) return heroArray;
            Weapon weapon = hero.Weapon;
            heroArray[11] = weapon.Card.AssetId;
            heroArray[12] = weapon.AttackDamage;
            heroArray[13] = weapon.Durability;
            heroArray[14] = weapon.IsWindfury ? 1 : 0;
            heroArray[15] = weapon.Poisonous ? 1 : 0;
            heroArray[16] = weapon.IsImmune ? 1 : 0;

            return heroArray;
        }

        public bool Equals(StateAbstraction other)
        {
            if (other == null)
                return false;

            if (!FieldEquals(other)) return false;

            for (int i = 0; i < _ids.Length; i++)
            {
                int[][] current = _ids[i];
                int[][] currentOther = other._ids[i];

                if (current?.Length != currentOther?.Length) return false;

                for (int j = 0; j < current?.Length; j++)
                {
                    int[] currentInner = current[j];
                    int[] currentInnerOther = currentOther[j];
                    if (currentInner == null)
                    {
                        if (currentInnerOther == null) continue;
                        return false;
                    }
                    if (currentInnerOther == null) return false;

                    for (int k = 0; k < currentInner.Length; k++)
                        if (currentInner[k] != currentInnerOther[k]) return false;
                }
            }

            if (_opDeckCount != other._opDeckCount) return false;

            if (_deck != null)
            {
                if (other._deck == null)
                    return false;

                if (!_deck.SequenceEqual(other._deck))
                    return false;
            }
            else if (other._deck != null)
                return false;

            return _actionHashCode == other._actionHashCode;

            //return true;
        }

        public bool FieldEquals(StateAbstraction other)
        {
            int[][] board = Board;
            int[][] otherBoard = other.Board;
            for (int i = 0; i < board.Length; i++)
            {
                int[] first = board[i];
                int[] second = otherBoard[i];
                if (first == null)
                {
                    if (second == null)
                        break;
                    return false;
                }
                if (second == null)
                    return false;
                if (!first.SequenceEqual(second)) return false;
            }

            int[][] opBoard = OpBoard;
            int[][] otherOpBoard = other.OpBoard;
            for (int i = 0; i < 7; i++)
            {
                int[] first = opBoard[i];
                int[] second = otherOpBoard[i];
                if (first == null)
                    return second == null;
                if (second == null)
                    return false;
                if (!first.SequenceEqual(second)) return false;
            }

            return true;
        }

        public override bool Equals(object obj)
        {
            return Equals(obj as StateAbstraction);
        }

        public string Hash
        {
            get
            {
                if (_hash != null)
                    return _hash;

                var sb = new StringBuilder();
                for (int i = 0; i < _ids.Length; i++)
                    for (int j = 0; j < _ids[i]?.Length; j++)
                        for (int k = 0; k < _ids[i][j]?.Length; k++)
                            sb.Append(_ids[i][j][k]);
                for (int i = 0; i < _boards.Length; i++)
                    for (int j = 0; j < _boards[i]?.Length; j++)
                        for (int k = 0; k < _boards[i][j]?.Length; k++)
                            sb.Append(_boards[i][j][k]);

                sb.Append(_actionHashCode);

                _hash = sb.ToString();

                return _hash;
            }
        }

        private string _hash;
        private int _hashCode;

        #region PlayableHash
        public const int PlayableHashLength = 29;

        public const int LengthMinionInPlay = LengthPlayable + 25;
        // 0 ID
        // 1 CONTROLLER_ID
        // 2 COST
        // 3 ECHO
        public const int LengthPlayable = 4;
        // 4 ATK
        // 5 HEALTH
        public const int LengthMinion = LengthPlayable + 2;

        //  TODO: Distinguish Zombeasts & Kazakus Potions
        public static int[] PlayableHash(IPlayable p, bool simple = false, bool returnToHand = false)
        {
            int[] arr;
            Zone zoneType = p.Zone?.Type ?? Zone.INVALID;

            if (p.Card.Type == CardType.MINION)
            {
                Minion m = (Minion)p;

                arr = zoneType == Zone.PLAY 
                    ? new int[LengthMinionInPlay] 
                    : new int[LengthMinion];

                if (p.Card.Name == "Zombeast")
                {
                    int temp = p.Card[GameTag.MODULAR_ENTITY_PART_2];
                    if (temp >= 10000)
                        arr[0] = p.Card[GameTag.MODULAR_ENTITY_PART_1] * 100000 + temp;
                    else if (temp >= 1000)
                        arr[0] = p.Card[GameTag.MODULAR_ENTITY_PART_1] * 10000 + temp;
                    else if (temp >= 100)
                        arr[0] = p.Card[GameTag.MODULAR_ENTITY_PART_1] * 1000 + temp;
                    else if (temp >= 10)
                        arr[0] = p.Card[GameTag.MODULAR_ENTITY_PART_1] * 100 + temp;
                    else
                        arr[0] = p.Card[GameTag.MODULAR_ENTITY_PART_1] * 10 + temp;
                }
                else if (returnToHand || !(simple && zoneType == Zone.PLAY && !m.IsDistinguishable()))
                    arr[0] = p.Card.AssetId;


                arr[LengthPlayable] = m.AttackDamage;
                arr[LengthPlayable + 1] = m.Health;

                if (zoneType == Zone.PLAY)
                {
                    arr[LengthPlayable + 2] = m.Damage;
                    //  TODO: deathrattle oop? && adjacent minion's zoneposition
                    if (!simple)
                    {
                        arr[LengthPlayable + 3] = m.ZonePosition;
                        arr[LengthPlayable + 4] = m.OrderOfPlay;
                    }
                    arr[LengthPlayable + 5] = m.IsExhausted ? 0 : 1;
                    arr[LengthPlayable + 6] = m.NumAttacksThisTurn;
                    arr[LengthPlayable + 7] = m.HasCharge ? 1 : 0;
                    arr[LengthPlayable + 8] = m.HasWindfury ? 1 : 0;
                    arr[LengthPlayable + 9] = m.HasTaunt ? 1 : 0;
                    arr[LengthPlayable + 10] = m.HasLifeSteal ? 1 : 0;
                    arr[LengthPlayable + 11] = m.HasStealth ? 1 : 0;
                    arr[LengthPlayable + 12] = m.HasDivineShield ? 1 : 0;
                    arr[LengthPlayable + 13] = m.Poisonous ? 1 : 0;
                    arr[LengthPlayable + 14] = m.IsFrozen ? 1 : 0;
                    arr[LengthPlayable + 15] = m.IsImmune ? 1 : 0;
                    arr[LengthPlayable + 16] = m.CantBeTargetedBySpells ? 1 : 0;
                    arr[LengthPlayable + 17] = m.HasDeathrattle ? 1 : 0;
                    //arr[20] = m[GameTag.CANNOT_ATTACK_HEROES];
                    arr[LengthPlayable + 18] = (int)m.Race;
                    arr[LengthPlayable + 19] = m.OngoingEffect != null ? 1 : 0;
                    arr[LengthPlayable + 20] = m.ActivatedTrigger != null ? 1 : 0;
                    if (p.AppliedEnchantments?.Count > 0)
                    {
                        Enchantment e = p.AppliedEnchantments[0];
                        arr[LengthPlayable + 21] = e.Card.AssetId;
                        arr[LengthPlayable + 22] = e.CapturedCard?.AssetId ?? 0;
                        //arr[25] = e[GameTag.TAG_SCRIPT_DATA_NUM_1];
                        //arr[26] = e[GameTag.TAG_SCRIPT_DATA_NUM_2];
                    }

                    arr[LengthPlayable + 23] = m.AttackableByRush ? 1 : 0;

                    // Silver Hand Recruit or Treant
                    arr[LengthPlayable + 24] = m.Card.AssetId == 1652 || m.Card.AssetId == 600 ? 1 : 0;
                }
            }
            else
            {
                arr = new int[LengthPlayable];
                arr[0] = p.Card.AssetId;
                // TODO: Kazakus Potions
            }
            arr[1] = p.Controller.Id;
            arr[2] = p.Cost;
            arr[3] = p[GameTag.GHOSTLY];

            return arr;
        }
        #endregion

        public static string CardHash(Card card)
        {
            var sb = new StringBuilder();
            sb.Append(card.AssetId);
            sb.Append(card.Cost);
            //sb.Append(card.Power.Count); //  TODO: InfoCardIds
            sb.Append(card.Text);
            sb.Append(card.LifeSteal);
            sb.Append(card.Deathrattle);
            sb.Append(card.Echo);
            if (card.Type != CardType.MINION) return sb.ToString();
            sb.Append(card.ATK);
            sb.Append(card.Health);
            sb.Append(card.Taunt);
            sb.Append(card.CantBeTargetedBySpells);
            sb.Append(card.Charge);
            sb.Append(card.Windfury);
            sb.Append(card.Stealth);
            sb.Append(card.Poisonous);
            sb.Append(card.Rush);
            return sb.ToString();
        }

        public override string ToString()
        {
            var sb = new StringBuilder();

            for (int i = 0; i < _boards.Length; i++)
            {
                if (_boards[i] == null) break;
                for (int j = 0; j < _boards[i].Length; j++)
                {
                    if (_boards[i][j] == null) break;
                    for (int k = 0; k < _boards[i][j].Length; k++)
                        sb.Append(_boards[i][j][k]);
                }
            }

            for (int i = 0; i < _ids.Length; i++)
            {
                if (_ids[i] == null) continue;
                for (int j = 0; j < _ids[i].Length; j++)
                {
                    if (_ids[i][j] == null) continue;
                    for (int k = 0; k < _ids[i][j].Length; k++)
                        sb.Append(_ids[i][j][k]);
                }
            }

            sb.Append(_actionHashCode);

            return sb.ToString();
        }

        public string GetInterpret
        {
            get
            {
                var sb = new StringBuilder();

                if (ChoiceInfo != null)
                {
                    // Choices
                    sb.Append("Choices: { ");
                    for (int i = 0; i < ChoiceInfo[0].Length; i++)
                        sb.Append($"{ChoiceInfo[0][i]} ");
                    sb.Append("}\n");

                    // Choice Ancillaries
                    if (ChoiceInfo[1][0] != 0)
                        sb.AppendLine($"Last Choice: {ChoiceInfo[1][0]}");
                    if (ChoiceInfo[1][1] != 0)
                        sb.AppendLine(
                            $"Next choices: {{ {ChoiceInfo[1][1]} {ChoiceInfo[1][2]} {ChoiceInfo[1][3]} }}");
                    if (ChoiceInfo[1].Length > 4)
                    {
                        sb.Append("Choice Targets: { ");
                        for (int i = 4; i < ChoiceInfo[1].Length; i++)
                            sb.Append($"{ChoiceInfo[1][i]}");
                        sb.Append("}\n");
                    }

                    sb.AppendLine();
                }

                var controller = Controller;
                sb.AppendLine("Controller:");
                sb.AppendLine($"Base Mana: {controller[0]}");
                sb.AppendLine($"Remaining Mana: {controller[1]}");
                sb.AppendLine($"Overload Locked: {controller[2]}");
                sb.AppendLine($"Overload Owed: {controller[3]}");
                sb.AppendLine();

                sb.AppendLine("Hand:");
                if (Hand.Length == 1 && Hand[0].Length == 1)
                    sb.AppendLine($"Count: {Hand[0][0]}");
                else
                    for (int i = 0; i < Hand.Length; i++)
                    {
                        if (Hand[i] == null) break;
                        sb.AppendLine(InterpretPlayableHash(Hand[i]));
                    }

                sb.AppendLine();

                sb.AppendLine("Hero Info:");
                sb.AppendLine(InterpretHeroInfo(Hero));
                sb.AppendLine();

                sb.AppendLine("Board:");
                for (int i = 0; i < Board.Length; i++)
                {
                    if (Board[i] == null) break;
                    sb.AppendLine(InterpretPlayableHash(Board[i]));
                }

                // TODO: OP Info and extras

                return sb.ToString();
            }
        }

        private static string InterpretPlayableHash(int[] playableHash)
        {
            var sb = new StringBuilder();
            sb.AppendLine($"Id: {playableHash[0]}");
            sb.AppendLine($"Cost: {playableHash[1]}");
            if (playableHash[2] == 1) sb.AppendLine("Ghostly Card");
            if (playableHash[4] == 0) return sb.ToString();
            sb.AppendLine($"ATK: {playableHash[3]}");
            sb.AppendLine($"Health: {playableHash[4]}");
            sb.AppendLine($"Damage: {playableHash[5]}");
            sb.AppendLine($"Zone Position: {playableHash[6]}");
            sb.AppendLine($"Order of Play: {playableHash[7]}");
            if (playableHash[8] == 0) sb.AppendLine("Exhausted");
            sb.AppendLine($"Num Attacked this turn: {playableHash[9]}");
            if (playableHash[10] == 1) sb.AppendLine("Charge");
            if (playableHash[11] == 1) sb.AppendLine("Windfury");
            if (playableHash[12] == 1) sb.AppendLine("Taunt");
            if (playableHash[13] == 1) sb.AppendLine("Lifesteal");
            if (playableHash[14] == 1) sb.AppendLine("Stealth");
            if (playableHash[15] == 1) sb.AppendLine("Divine Shield");
            if (playableHash[16] == 1) sb.AppendLine("Poisonous");
            if (playableHash[17] == 1) sb.AppendLine("Frozen");
            if (playableHash[18] == 1) sb.AppendLine("Immune");
            if (playableHash[19] == 1) sb.AppendLine("Can't be targeted by spells");
            if (playableHash[20] == 1) sb.AppendLine("Deathrattle");
            if (playableHash[21] > 0) sb.AppendLine($"Race: {playableHash[21]}");
            if (playableHash[22] == 1) sb.AppendLine("This has Ongoing Effect");
            if (playableHash[23] == 1) sb.AppendLine("This has Activated Trigger");
            if (playableHash[24] > 0) sb.AppendLine($"The first applied enchantment's id: {playableHash[24]}");
            if (playableHash[25] > 0) sb.AppendLine($"The first applied enchantment's script1: {playableHash[25]}");
            if (playableHash[26] > 0) sb.AppendLine($"The first applied enchantment's script2: {playableHash[26]}");
            if (playableHash[27] == 1) sb.AppendLine("Attackable by Rush");
            if (playableHash[28] == 1) sb.AppendLine("Silver Hand Recruit or Treant");

            return sb.ToString();
        }

        private static string InterpretHeroInfo(int[] heroInfo)
        {
            var sb = new StringBuilder();
            sb.AppendLine($"Class: {heroInfo[0]}");
            sb.AppendLine($"Health: {heroInfo[1]}");
            sb.AppendLine($"Armour: {heroInfo[2]}");
            sb.AppendLine($"ATK: {heroInfo[3]}");
            if (heroInfo[4] == 1) sb.AppendLine("Exhausted");
            if (heroInfo[5] == 1) sb.AppendLine("Stealth");
            if (heroInfo[6] == 1) sb.AppendLine("Immune");
            sb.AppendLine($"HeroPower Id: {heroInfo[7]}");
            sb.AppendLine($"HeroPower Cost: {heroInfo[8]}");
            if (heroInfo[4] == 0) sb.AppendLine("HeroPower Exhausted");

            if (heroInfo[10] == 0) return sb.ToString();
            sb.AppendLine($"Weapon Id: {heroInfo[10]}");
            sb.AppendLine($"Weapon ATK: {heroInfo[11]}");
            sb.AppendLine($"Weapon Durability: {heroInfo[12]}");
            if (heroInfo[13] == 1) sb.AppendLine("Weapon Windfury");
            if (heroInfo[14] == 1) sb.AppendLine("Weapon Poisonous");
            if (heroInfo[15] == 1) sb.AppendLine("Weapon Immune");
            return sb.ToString();
        }

        public static bool operator ==(StateAbstraction abstraction1, StateAbstraction abstraction2)
        {
            return EqualityComparer<StateAbstraction>.Default.Equals(abstraction1, abstraction2);
        }

        public static bool operator !=(StateAbstraction abstraction1, StateAbstraction abstraction2)
        {
            return !(abstraction1 == abstraction2);
        }

        #region InformationSet
        public Information ExtractPrivateInformation(in ReadOnlySpan<IPlayable> hand)
        {
	        if (!Complete)
	        {
		        var buffer = new int[hand.Length][];

		        for (int i = 0; i < buffer.Length; i++)
		        {
			        var hash = PlayableHash(hand[i], true);

			        buffer[i] = hash;
		        }

		        Array.Sort(buffer, IntArrayComparer);
				OpHand = buffer;
	        }

            // Extract Information.
            Information info = new Information(OpHand, in hand);

            Complete = false;
            
            // Hide private information of the opponent.
            OpHand = new[] {new[] {OpHand.Length}};

            // Reset the cache for hash code.
            _hashCode = 0;


            return info;
        }
        #endregion
    }
}
