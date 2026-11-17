export const displayPlan = snapshot => snapshot.review_plan ?? snapshot.current_plan;
const targetKeys = ['participant_version','constraint_version','evidence_version','plan_revision','content_hash'];
export const sameTarget = (a,b) => !!a && !!b && targetKeys.every(key => a[key] === b[key]);
