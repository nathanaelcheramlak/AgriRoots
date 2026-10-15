"""Legacy delivery routes cannot publish new household advice in Phase 1."""
from fastapi import Depends, HTTPException
from src.auth.dependencies import get_current_user

REVIEW_NOTICE = ("Household-specific advice requires officer review and explicit release. "
                 "Contact your extension office; released advice is available in /advisories.")


def require_review_workflow(user=Depends(get_current_user)):
    raise HTTPException(status_code=409, detail=REVIEW_NOTICE)


# A closed, deterministic educational catalogue keeps the boundary enforceable:
# arbitrary prompts, images and transcripts never reach an advice-generating model.
EDUCATION = {
    "what is crop rotation?": "Crop rotation means growing different crops on the same plot in successive seasons.",
    "what is compost?": "Compost is decomposed organic material.",
    "what is agroclimate?": "Agroclimate describes climate conditions relevant to agriculture.",
}

EDUCATION_AM = {
    "የሰብል ፈረቃ ምንድን ነው?": "የሰብል ፈረቃ በአንድ ማሳ ላይ በተከታታይ ወቅቶች የተለያዩ ሰብሎችን ማምረት ነው።",
    "ኮምፖስት ምንድን ነው?": "ኮምፖስት የበሰበሰ ኦርጋኒክ ቁስ ነው።",
    "አግሮክላይማት ምንድን ነው?": "አግሮክላይማት ለግብርና አስፈላጊ የሆኑ የአየር ንብረት ሁኔታዎችን ይገልጻል።",
}
REVIEW_NOTICE_AM = "ለቤተሰብዎ የሚሰጥ የእርሻ ምክር በባለሙያ መገምገምና መፈቀድ አለበት። የተለቀቀ ምክር በ /advisories ይገኛል። የግብርና ጽሕፈት ቤትዎን ያነጋግሩ።"
