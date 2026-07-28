using System;
using System.Collections.Generic;
using System.Text;
using SabberStoneCoreAi.MCGS.Heuristics;
using SabberStoneCore.Model;
using SabberStoneCore.Model.Entities;
using SabberStoneCore.Tasks.PlayerTasks;

namespace SabberStoneCoreAi.MCGS.Abstraction
{
    public class ActionAbstraction : IEquatable<ActionAbstraction>/*, IEqualityComparer<PlayerTask>*/
    {
        private readonly PlayerTaskType _type;
        //private readonly int _controllerId;    //  Entity ID
        //private readonly int _targetControllerId;
        private readonly int? _sourceId;
        private readonly int? _targetId;
        private readonly int _subOption;
        private readonly int[] _sourceHash = new int[0];
        private readonly int[] _targetHash = new int[0];
        private readonly int? _zonePosition;
        //private readonly string[] _choices;
        private readonly string _choice;
        private readonly int _choiceId;

#if TRACE
        private readonly string _sourceName;
        private readonly string _targetName;
#endif

        //public bool IsFixed => _action != null;

        public ActionAbstraction(PlayerTask action, 
            Dictionary<int, int[]> hashDic,
            bool ignorePosition = false)
        {
            if (action == null)
                throw new ArgumentNullException();

            _type = action.PlayerTaskType;
            //_controllerId = action.Controller.Id;
            _subOption = action.ChooseOne > 0 ? action.ChooseOne : 0;
            var player = action.Controller;
            switch (_type)
            {
                case PlayerTaskType.CHOOSE:
                    var choose = (ChooseTask)action;
                    //_choices = choose.Choices.Select(e => action.Game.IdEntityDic[e].Card.Name).ToArray();
                    _choiceId = choose.Choices[0];
                    _choice = action.Game.IdEntityDic[_choiceId].Card.Name;
                    break;
                case PlayerTaskType.HERO_ATTACK:
                    _sourceId = player.Hero.Id;
                    _targetId = action.Target.Id;
                    //_targetHash = StateAbstraction.PlayableHash(action.Game.IdEntityDic[action.Target.Id], ignorePosition);
                    _targetHash = hashDic[_targetId.Value];
                    break;
                case PlayerTaskType.HERO_POWER:
                    _sourceId = player.Hero.HeroPower.Id;
                    _targetId = action.Target?.Id;
                    if (_targetId != null)
                        //_targetHash = StateAbstraction.PlayableHash(action.Game.IdEntityDic[_targetId.Value], ignorePosition);
                        _targetHash = hashDic[_targetId.Value];
                    break;
                case PlayerTaskType.MINION_ATTACK:
                    _sourceId = action.Source.Id;
                    _targetId = action.Target.Id;
                    //_sourceHash = StateAbstraction.PlayableHash(action.Game.IdEntityDic[action.Source.Id], ignorePosition);
                    //_targetHash = StateAbstraction.PlayableHash(action.Game.IdEntityDic[action.Target.Id], ignorePosition);
                    _sourceHash = hashDic[_sourceId.Value];
                    _targetHash = hashDic[_targetId.Value];
                    break;
                case PlayerTaskType.PLAY_CARD:
                    _sourceId = action.Source.Id;
                    _targetId = action.Target?.Id;
                    //_sourceHash = StateAbstraction.PlayableHash(action.Game.IdEntityDic[action.Source.Id], ignorePosition);
                    _sourceHash = hashDic[_sourceId.Value];
                    if (_targetId != null)
                    {
                        //var target = action.Game.IdEntityDic[_targetId.Value];
                        //_targetHash = StateAbstraction.PlayableHash(target, ignorePosition, CardCategory.ReturnToHand.Contains(action.Source.Card.AssetId));
                        var hash = hashDic[_targetId.Value];
                        if (CardCategory.ReturnToHand.Contains(action.Source.Card.AssetId))
                        {
                            var newHash = new int[hash.Length];
                            Buffer.BlockCopy(hash, 0, newHash, 0, hash.Length * sizeof(int));
                            newHash[0] = action.Target.Card.AssetId;
                            hash = newHash;
                        }
                        _targetHash = hash;
                        //_targetControllerId = target.Controller.Id;
                    }

                    //if (action.Source.Card.Type == CardType.MINION)
                    //{
                    //    //if (!ignorePosition || CardCategory.AdjacentEffectMinions.Contains(action.Source.Id))
                    //    //{
                    //    //    _zonePosition = ((PlayCardTask) action).ZonePosition;
                    //    //    if (_zonePosition == -1)
                    //    //        _zonePosition = player.BoardZone.Count;
                    //    //}

                    //}
                    _zonePosition = ((PlayCardTask) action).ZonePosition;
                    if (_zonePosition == -1)
                        _zonePosition = player.BoardZone.Count;

                    break;
				case PlayerTaskType.END_TURN:
					IsEndTurnAction = true;
					break;
            }

#if TRACE
            if (_sourceId != null)
                _sourceName = action.Game.IdEntityDic[_sourceId.Value].Card.Name;
            if (_targetId != null)
                _targetName = action.Game.IdEntityDic[_targetId.Value].Card.Name;
#endif
        }

        public ActionAbstraction(PlayerTask action, bool ignorePosition)
        {
            _type = action.PlayerTaskType;

            if (action.HasSource)
            {
                int id = action.Source.Id;
                _sourceId = id;
                _sourceHash = StateAbstraction.PlayableHash(action.Game.IdEntityDic[id], ignorePosition);
            }

            if (action.HasTarget)
            {
                int id = action.Target.Id;
                _targetId = id;
                _targetHash = StateAbstraction.PlayableHash(action.Game.IdEntityDic[id], ignorePosition, _sourceId != null &&
                    CardCategory.ReturnToHand.Contains(action.Source.Card.AssetId));
            }

            switch (action)
            {
                case ChooseTask chooseTask:
                    //_choices = chooseTask.Choices.Select(e => action.Game.IdEntityDic[e].Card.Name).ToArray();
                    _choiceId = chooseTask.Choices[0];
                    _choice = action.Game.IdEntityDic[_choiceId].Card.Name;
                    break;
                case EndTurnTask _:
                    IsEndTurnAction = true;
                    break;
                case PlayCardTask playCardTask:
                    _zonePosition = playCardTask.ZonePosition;
                    break;
            }

        }

        public ActionAbstraction(PlayerTaskType type, int controllerId, int? sourceId = null, int? targetId = null,
            int? zonePosition = null, int subOption = 0)
        {
            _type = type;
            //_controllerId = controllerId;
            _sourceId = sourceId;
            _targetId = targetId;
            _subOption = subOption;
            _zonePosition = zonePosition;
        }

        private ActionAbstraction(ActionAbstraction other)
        {
            _type = other._type;
            //_controllerId = other._controllerId;
            _sourceId = other._sourceId;
            _targetId = other._targetId;
            _subOption = other._subOption;
            _sourceHash = new int[other._sourceHash.Length];
            _targetHash = new int[other._targetHash.Length];
            _zonePosition = other._zonePosition;
            //_choices = other._choices;
            _choice = other._choice;
            _choiceId = other._choiceId;
            //_sourceName = other._sourceName;
            //_targetName = other._targetName;

            Array.Copy(other._sourceHash, _sourceHash, _sourceHash.Length);
            Array.Copy(other._targetHash, _targetHash, _targetHash.Length);
        }
		
		public readonly bool IsEndTurnAction;

        public ActionAbstraction GetSimplified()
        {
            var clone = new ActionAbstraction(this);

            if (_sourceHash.Length > 7)
            {
                clone._sourceHash[6] = 0;
                clone._sourceHash[7] = 0;
            }

            if (_targetHash.Length > 7)
            {
                clone._targetHash[6] = 0;
                clone._targetHash[7] = 0;
            }

            return clone;
        }

        public PlayerTask GetSabberPlayerTask(Game g)
        {
            var c = g.CurrentPlayer;

            switch (_type)
            {
                case PlayerTaskType.CHOOSE:
                    return ChooseTask.Pick(c, _choiceId);
                case PlayerTaskType.END_TURN:
                    return EndTurnTask.Any(c);
                case PlayerTaskType.HERO_ATTACK:
                    return HeroAttackTask.Any(c, (ICharacter)g.IdEntityDic[_targetId ?? -1], true);
                case PlayerTaskType.HERO_POWER:
                    return HeroPowerTask.Any(c, (ICharacter)(_targetId != null ? g.IdEntityDic[_targetId.Value] : null), _subOption, true);
                case PlayerTaskType.MINION_ATTACK:
                    return MinionAttackTask.Any(c, g.IdEntityDic[_sourceId.Value], (ICharacter)g.IdEntityDic[_targetId.Value],
                        true);
                case PlayerTaskType.PLAY_CARD:
                    return PlayCardTask.Any(c, g.IdEntityDic[_sourceId.Value], (ICharacter)(_targetId != null ? g.IdEntityDic[_targetId.Value] : null),
                        _zonePosition ?? -1, _subOption, true);
                default:
                    throw new NotImplementedException();
            }
        }

        public override string ToString()
        {
            var sb = new StringBuilder();
            //sb.Append($"[{_controllerId}]");
            sb.Append($"[{_type}]");
            if (_sourceId != null)
#if TRACE
                sb.Append($"[{_sourceName}]");
#else
                sb.Append($"[{_sourceId}]");
#endif
            if (_targetId != null)
#if TRACE
                sb.Append($"=>[{_targetName}]");
#else
                sb.Append($"=>[{_targetId}]");
#endif
            //if (_choices != null)
            //    foreach (string choice in _choices)
            //        sb.Append($"[{choice}]");
            if (_choice != null)
                sb.Append(_choice);
            if (_zonePosition != null)
                sb.Append($"[P:{_zonePosition}]");
            if (_subOption > 0)
                sb.Append($"[C:{_subOption}]");
            return sb.ToString();
        }

        public string ActionPrint(Game g)
        {
            var c = g.CurrentPlayer;
            var name = c.Name;
            switch (_type)
            {
                case PlayerTaskType.CHOOSE:
                    return $"[{name}] chose {_choice}";
                case PlayerTaskType.END_TURN:
                    return $"[{name}] ended his turn.";
                case PlayerTaskType.HERO_ATTACK:
                    return $"[{name}]'s {c.Hero} attacked {g.IdEntityDic[_targetId.Value]}";
                case PlayerTaskType.HERO_POWER:
                    return $"[{name}] used {c.Hero.HeroPower}" + 
                           $"{(_targetId != null ? $" to {g.IdEntityDic[_targetId.Value]}" : "")}" + 
                           $"{(c.Hero.HeroPower.ChooseOne ? $" with SubOption: {_subOption}" : "")}";
                case PlayerTaskType.MINION_ATTACK:
                    return $"[{name}]'s {g.IdEntityDic[_sourceId.Value]} attacked {g.IdEntityDic[_targetId.Value]}";
                case PlayerTaskType.PLAY_CARD:
                    if (g.IdEntityDic[_sourceId.Value] is Minion m)
                        return $"[{name}] played {m} to Position {_zonePosition}" + 
                               $"{(_targetId != null ? $" and targeted {g.IdEntityDic[_targetId.Value]}" : "")}" + 
                               $" {(m.Card.ChooseOne ? $" with SubOption: {_subOption}" : "")}";
                    else
                        return $"[{name}] played {g.IdEntityDic[_sourceId.Value]}" + 
                               $"{(_targetId != null ? $" to {g.IdEntityDic[_targetId.Value]}" : "")}" + 
                               $"{(g.IdEntityDic[_sourceId.Value].Card.ChooseOne ? $" with SubOption: {_subOption}" : "")}";
                default:
                    throw new ArgumentOutOfRangeException();
            }
        }
#region equals
        //public bool Equals(PlayerTask a, PlayerTask b)
        //{
        //    //var x = new ActionAbstraction(a);
        //    //var y = new ActionAbstraction(b);
        //    //return x.Equals(y);


        //    return GetEquals(a, b);
        //}
        //public int GetHashCode(PlayerTask a)
        //{
        //    var x = new ActionAbstraction(a);
        //    return x.GetHashCode();
        //}

        public bool Equals(ActionAbstraction other)
        {
            if (_choice != null)
                return _choice == other._choice;
            //&&
            //_controllerId == other._controllerId;

            if (_type != other._type)
                return false;

            var source = _sourceHash;
            var otherHash = other._sourceHash;
            if (source.Length != otherHash.Length)
                return false;
            for (int i = 0; i < source.Length; i++)
                if (source[i] != otherHash[i])
                    return false;

            source = _targetHash;
            otherHash = other._targetHash;
            if (source.Length != otherHash.Length)
                return false;
            for (int i = 0; i < source.Length; i++)
                if (source[i] != otherHash[i])
                    return false;

            return
                //_targetControllerId == other._targetControllerId &&
                //_controllerId == other._controllerId &&
                _subOption == other._subOption &&
                _zonePosition == other._zonePosition;
        }

        public override bool Equals(object obj)
        {
            return Equals((ActionAbstraction)obj);
        }

        private int? _hash;

        public override int GetHashCode()
        {
	        if (_hash != null)
		        return _hash.Value;

			unchecked
			{
				var hashCode = (int)_type;
				hashCode = (hashCode * 397) ^ _subOption;
				hashCode = (hashCode * 397) ^ (_sourceHash != null ? _sourceHash.GetHashCode() : 0);
				hashCode = (hashCode * 397) ^ (_targetHash != null ? _targetHash.GetHashCode() : 0);
				hashCode = (hashCode * 397) ^ _zonePosition.GetHashCode();
				hashCode = (hashCode * 397) ^ (_choice?.GetHashCode() ?? 0);
				_hash = hashCode;
				return hashCode;
			}

            //var hash = HashCode.Combine((int)_type, /*_controllerId,*/ /*_targetControllerId,*/ _subOption, Utils.IntArrayComparer.ArrayHashCode(_sourceHash), Utils.IntArrayComparer.ArrayHashCode(_targetHash), _zonePosition,
            //    _choice/*_choice != null ? string.Join("",_choices) : null*/);

            //_hash = hash;

            //return hash;
        }

        public static bool operator ==(ActionAbstraction a, ActionAbstraction b)
        {
            if (ReferenceEquals(a, b)) return true;

            if (ReferenceEquals(a, null) || ReferenceEquals(b, null))
                return false;

            return a.Equals(b);
        }

        public static bool operator !=(ActionAbstraction a, ActionAbstraction b) => !(a == b);

        public static bool GetEquals(PlayerTask a, PlayerTask b)
        {
            if (a.GetType() != b.GetType())
                return false;

            if (a.Controller.Id != b.Controller.Id)
                return false;

            switch (a)
            {
                case ChooseTask chooseTask:
                {
                    var other = (ChooseTask)b;
                    return chooseTask.Choices[0] == other.Choices[0];
                }
                case EndTurnTask endTurnTask:
                    return true;
                case HeroAttackTask heroAttackTask:
                {
                    var other = (HeroAttackTask)b;
                    return
                        heroAttackTask.Target.Id == other.Target.Id;
                }
                case HeroPowerTask heroPowerTask:
                {
                    var other = (HeroPowerTask)b;
                    return
                        heroPowerTask.Target?.Id == other.Target?.Id;

                }
                case MinionAttackTask minionAttackTask:
                {
                    var other = (MinionAttackTask)b;
                    return
                        minionAttackTask.Source.Card.Id == other.Source.Card.Id &&
                        minionAttackTask.Target.Card.Id == other.Target.Card.Id;
                }
                case PlayCardTask playCardTask:
                {
                    var other = (PlayCardTask)b;
                    return
                        playCardTask.Source.Id == other.Source.Id &&
                        playCardTask.Target?.Id == other.Target?.Id &&
                        playCardTask.ZonePosition == other.ZonePosition &&
                        playCardTask.ChooseOne == other.ChooseOne;
                }

                default:
                    return true;
            }
        }

#endregion
    }
}
