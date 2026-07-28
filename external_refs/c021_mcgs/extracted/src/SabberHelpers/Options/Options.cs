using System;
using System.Collections.Generic;
using SabberStoneCoreAi.MCGS.Utils;
using SabberStoneCore.Model.Entities;
using SabberStoneCore.Tasks.PlayerTasks;

namespace SabberStoneCoreAi.MCGS.SabberHelper.Option
{
    public class Options : IEquatable<Options>
    {
        //public Controller Controller;

        private HeroPowerOption _heroPowerOption;
        private bool _endTurnTaskRemoved;

        public int AttackerCount { get; set; }

        public int PlayableCount { get; set; }

        //public int TotalCount { get; set; } = 1;

        //public int PlayCount { get; set; }
        //public int AttackCount { get; set; }
        //public int heroPowerCount { get; set; }
        //private int endCount = 1;
        private bool _isHeroPowerUseable;

        public bool IsHeroPowerUseable
        {
            get => _isHeroPowerUseable;
            set
            {
                _isHeroPowerUseable = value;
                //if (!value)
                //{
                //    TotalCount -= _heroPowerOption.Count;
                //    heroPowerCount = 0;
                //}
            }
        }

        public bool EndTurnTaskRemoved
        {
            get => _endTurnTaskRemoved;
            set
            {
                //if (_endTurnTaskRemoved == value) return;

                //if (value)
                //{
                //    TotalCount--;
                //    endCount = 0;
                //}
                //else
                //{
                //    TotalCount++;
                //    endCount = 1;
                //}

                _endTurnTaskRemoved = value;
            }
        }

        public List<PlayCardOption> PlayCardOptions { get; set; }
        //public PlayCardOptionContainer PlayCardOptions { get; }

        public HeroPowerOption HeroPowerOption
        {
            get => _heroPowerOption;
            set
            {
                _heroPowerOption = value;
                IsHeroPowerUseable = true;
                //TotalCount += value.Count;
                //heroPowerCount = value.Count;
            }
        }

        public List<AttackOption> AttackOptions { get; set; }

        public bool HasNoAvailableActions =>
            PlayCardOptions.Count == 0 && AttackOptions.Count == 0 && !IsHeroPowerUseable;

        public Options(in Controller c)
        {
            //Controller = c;
            PlayCardOptions = new List<PlayCardOption>(c.HandZone.Count);
            //PlayCardOptions = new PlayCardOptionContainer(c.HandZone.Count);
            AttackOptions = new List<AttackOption>(c.BoardZone.Count + 1);
        }

        /// <summary>
        /// Gets a set of all <see cref="PlayerTask"/>s that can be generated from this object.
        /// This should be equivalent to <see cref="Controller.Options(bool)"/>.
        /// </summary>
        public PlayerTask[] Translate(in Controller c)
        {
            //Controller c = Controller;

            //int total = 0;
            //for (int i = 0; i < PlayCardOptions.Count; i++)
            //    total += PlayCardOptions[i].Count;
            //for (int i = 0; i < AttackOptions.Count; i++)
            //    total += AttackOptions[i].Count;
            //if (IsHeroPowerUseable)
            //    total += HeroPowerOption.Count;
            //if (!EndTurnTaskRemoved)
            //    total += 1;

            int playCount = 0;
            int heroPowerCount = IsHeroPowerUseable ? HeroPowerOption.Count : 0;
            int attackCount = 0;
            int end = EndTurnTaskRemoved ? 0 : 1;

            for (int i = 0; i < PlayCardOptions.Count; i++)
                playCount += PlayCardOptions[i].Count;
            for (int i = 0; i < AttackOptions.Count; i++)
                attackCount += AttackOptions[i].Count;

            var result = new PlayerTask[playCount + heroPowerCount + attackCount + end];

            int start = 0;
            for (int i = 0; i < PlayCardOptions.Count; i++)
            {
                int length = PlayCardOptions[i].Count;
                var span = new Span<PlayerTask>(result, start, length);
                PlayCardOptions[i].Translate(c, in span);
                start += length;
            }

            if (heroPowerCount > 0)
            {
                var span = new Span<PlayerTask>(result, start, heroPowerCount);
                HeroPowerOption.Translate(c, in span);
                start += heroPowerCount;
            }

            for (int i = 0; i < AttackOptions.Count; i++)
            {
                int length = AttackOptions[i].Count;
                var span = new Span<PlayerTask>(result, start, length);
                AttackOptions[i].Translate(c, in span);
                start += length;
            }

            if (!EndTurnTaskRemoved)
            {
                result[start] = EndTurnTask.Any(c);
            }

            return result;


            //var resultList = new List<PlayerTask>(total);

            //foreach (PlayCardOption playOption in PlayCardOptions)
            //    resultList.AddRange(playOption.Translate(c));

            //if (IsHeroPowerUseable)
            //    resultList.AddRange(HeroPowerOption.Translate(c));

            //foreach (AttackOption attackOption in AttackOptions)
            //    resultList.AddRange(attackOption.Translate(c));

            //if (!EndTurnTaskRemoved)
            //    resultList.Add(EndTurnTask.Any(c));

            //return resultList.ToArray();
        }

        /// <summary>
        /// Gets a <see cref="PlayerTask"/>, randomly selected from all possible options.
        /// </summary>
        public PlayerTask GetRandom(in Controller c, Random rnd)
        {
            int playCount = 0;
            int heroPowerCount = IsHeroPowerUseable ? HeroPowerOption.Count : 0;
            int attackCount = 0;
            int end = EndTurnTaskRemoved ? 0 : 1;

            for (int i = 0; i < PlayCardOptions.Count; i++)
                playCount += PlayCardOptions[i].Count;
            for (int i = 0; i < AttackOptions.Count; i++)
                attackCount += AttackOptions[i].Count;

            int roll = rnd.Next(playCount + heroPowerCount + attackCount + end);

            if (roll < playCount)
                return PlayCardOptions.GetWeightedRandom(p => p.Count, rnd, playCount).GetRandom(c, rnd);
                //return PlayCardOptions.GetWeightedRandom(rnd, playCount).GetRandom(c, rnd);

            roll -= playCount;
            if (roll < attackCount)
                return AttackOptions.GetWeightedRandom(p => p.Count, rnd, attackCount).GetRandom(c, rnd);

            roll -= attackCount;
            if (roll < heroPowerCount)
                return HeroPowerOption.GetRandom(c, rnd);

            return EndTurnTask.Any(c);
        }

        public void AddPlayCardOption(in PlayCardOption pOption)
        {
            PlayableCount++;
            PlayCardOptions.Add(pOption);
            //TotalCount += pOption.Count;
            //PlayCount += pOption.Count;
        }

        public void AddAttackOption(in AttackOption aOption)
        {
            AttackerCount++;
            AttackOptions.Add(aOption);
            //TotalCount += aOption.Count;
            //AttackCount += aOption.Count;
        }

        public void Reset(in Controller controller)
        {
            //Controller = controller;
            _endTurnTaskRemoved = false;
            _isHeroPowerUseable = false;
            PlayCardOptions?.Clear();
            AttackOptions?.Clear();
            AttackerCount = 0;
            PlayableCount = 0;
        }

        public bool Equals(Options other)
        {
            if (PlayCardOptions.Count != other.PlayCardOptions.Count)
                return false;
            if (AttackOptions.Count != other.AttackOptions.Count)
                return false;

            for (int i = 0; i < PlayCardOptions.Count; i++)
            {
                PlayCardOption a = PlayCardOptions[i];
                PlayCardOption b = other.PlayCardOptions[i];
                if (!PlayCardOption.Equals(in a, in b)) return false;
            }

            for (int i = 0; i < AttackOptions.Count; i++)
            {
                AttackOption a = AttackOptions[i];
                AttackOption b = other.AttackOptions[i];
                if (!AttackOption.Equals(in a, in b)) return false;
            }

            if (IsHeroPowerUseable != other.IsHeroPowerUseable)
                return false;

            return EndTurnTaskRemoved == other.EndTurnTaskRemoved;
        }

        public override bool Equals(object obj)
        {
            if (ReferenceEquals(null, obj)) return false;
            if (ReferenceEquals(this, obj)) return true;
            if (obj.GetType() != this.GetType()) return false;
            return Equals((Options) obj);
        }

        public override int GetHashCode()
        {
            unchecked
            {
                int hashCode = _endTurnTaskRemoved.GetHashCode();
                hashCode = (hashCode * 397) ^ _isHeroPowerUseable.GetHashCode();
                for (int i = 0; i < PlayCardOptions.Count; i++)
                    hashCode = (hashCode * 397) ^ PlayCardOptions[i].GetHashCode();

                for (int i = 0; i < AttackOptions.Count; i++)
                    hashCode = (hashCode * 397) ^ AttackOptions[i].GetHashCode();

                return hashCode;
            }
        }

        public override string ToString()
        {
            return
                $"[P:{PlayCardOptions.Count} A:{AttackOptions.Count} H:{(IsHeroPowerUseable ? "T" : "F")} E:{(EndTurnTaskRemoved ? "F" : "T")}]";
        }
    }
}
