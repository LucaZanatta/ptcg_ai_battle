using System;
using SabberStoneCoreAi.MCGS.Utils;
using SabberStoneCore.Model.Entities;
using SabberStoneCore.Tasks.PlayerTasks;

namespace SabberStoneCoreAi.MCGS.SabberHelper.Option
{
    public readonly struct PlayCardOption
    {
        public readonly IPlayable Source;
        public readonly ICharacter[] Targets;
        public readonly int ZonePositionRange;
        public readonly int SubOption;

        //public int Count
        //{
        //    get
        //    {
        //        int t = Targets?.Length ?? 1;
        //        int p = ZonePositionRange + 1;

        //        return t * p;
        //    }
        //}

        public readonly int Count;

        public bool HasTargets => Targets != null;

        public PlayCardOption(IPlayable source, int subOption)
        {
            Source = source;
            Targets = null;
            ZonePositionRange = 0;
            SubOption = subOption;

            Count = 1;
        }

        public PlayCardOption(IPlayable source, ICharacter[] targets, int subOption)
        {
            Source = source;
            Targets = targets;
            ZonePositionRange = 0;
            SubOption = subOption;

            Count = targets?.Length ?? 1;
        }

        public PlayCardOption(IPlayable source, ICharacter[] targets, int zonePosRange, int subOption)
        {
            Source = source;
            Targets = targets;
            ZonePositionRange = zonePosRange;
            SubOption = subOption;

            Count = (targets?.Length ?? 1) * (zonePosRange + 1);
        }

        public PlayCardOption ChangeTargets(ICharacter[] newTargets)
        {
            return new PlayCardOption(Source, newTargets, ZonePositionRange, SubOption);
        }

        public PlayCardOption RemoveZonePosRange()
        {
            return new PlayCardOption(Source, Targets, SubOption);
        }

        public PlayCardTask[] Translate(Controller c)
        {
            PlayCardTask[] result;
            //Controller c = Source.Controller;
                 
            if (ZonePositionRange == 0)
            {
                if (Targets == null)
                {
                    result = new PlayCardTask[1];
                    result[0] = PlayCardTask.Any(c, Source, chooseOne: SubOption, skipPrePhase: true);
                    return result;
                }
                else
                {
                    result = new PlayCardTask[Targets.Length];
                    for (int i = 0; i < Targets.Length; i++)
                        result[i] = PlayCardTask.Any(c, Source, Targets[i], chooseOne: SubOption, skipPrePhase: true);

                    return result;
                }
            }
            else if (Targets == null)
            {
                result = new PlayCardTask[ZonePositionRange + 1];
                for (int i = 0; i <= ZonePositionRange; i++)
                    result[i] = PlayCardTask.Any(c, Source, null, i, SubOption, true);
                return result;
            }
            else
            {
                result = new PlayCardTask[Targets.Length * (ZonePositionRange + 1)];

                for (int i = 0; i < Targets.Length; i++)
                for (int j = 0; j <= ZonePositionRange; j++)
                    result[(ZonePositionRange + 1) * i + j] =
                        PlayCardTask.Any(c, Source, Targets[i], j, SubOption, true);


                return result;
            }
        }

        public void Translate(Controller c, in Span<PlayerTask> result)
        {
            if (ZonePositionRange == 0)
                if (Targets == null)
                    result[0] = PlayCardTask.Any(c, Source, null, c.BoardZone.Count, SubOption, true);
                else
                    for (int i = 0; i < Targets.Length; i++)
                        result[i] = PlayCardTask.Any(c, Source, Targets[i], c.BoardZone.Count, SubOption, true);
            else if (Targets == null)
                for (int i = 0; i <= ZonePositionRange; i++)
                    result[i] = PlayCardTask.Any(c, Source, null, i, SubOption, true);
            else
                for (int i = 0; i < Targets.Length; i++)
                for (int j = 0; j <= ZonePositionRange; j++)
                    result[(ZonePositionRange + 1) * i + j] =
                        PlayCardTask.Any(c, Source, Targets[i], j, SubOption, true);
        }

        public PlayCardTask GetRandom(Controller c, Random rnd)
        {
            return Targets == null
                ? ZonePositionRange == 0
                    ? PlayCardTask.Any(c, Source, null, c.BoardZone.Count, SubOption, true)
                    : PlayCardTask.Any(c, Source, null, rnd.Next(0, ZonePositionRange + 1),
                        SubOption, true)
                : ZonePositionRange == 0
                    ? PlayCardTask.Any(c, Source, Targets.Random(rnd), c.BoardZone.Count, SubOption, true)
                    : PlayCardTask.Any(c, Source, Targets.Random(rnd),
                        rnd.Next(0, ZonePositionRange + 1),
                        SubOption, true);
        }

        public override string ToString()
        {
            return $"{Source}";
        }

        public static bool Equals(in PlayCardOption a, in PlayCardOption b)
        {
            return
                a.Count == b.Count &&
                a.Source.Card.AssetId == b.Source.Card.AssetId &&
                a.Targets?.Length == b.Targets?.Length &&
                a.ZonePositionRange == b.ZonePositionRange && 
                a.SubOption == b.SubOption;
        }

        public override int GetHashCode()
        {
            var hashCode = Count;

            hashCode = (hashCode * 17) ^ (Source?.Card.AssetId ?? 0);
            hashCode = (hashCode * 17) ^ (Targets?.Length ?? 0);
            hashCode = (hashCode * 17) ^ ZonePositionRange;
            hashCode = (hashCode * 17) ^ SubOption;

            return hashCode;
        }

        //public override bool Equals(object obj)
        //{
        //    if (ReferenceEquals(null, obj)) return false;
        //    return obj is PlayCardOption other && Equals(other);
        //}

        //public override int GetHashCode()
        //{
        //    unchecked
        //    {
        //        var hashCode = (Source != null ? Source.GetHashCode() : 0);
        //        hashCode = (hashCode * 397) ^ (Targets != null ? Targets.GetHashCode() : 0);
        //        hashCode = (hashCode * 397) ^ ZonePositionRange;
        //        hashCode = (hashCode * 397) ^ SubOption;
        //        hashCode = (hashCode * 397) ^ Count;
        //        return hashCode;
        //    }
        //}
    }
}
