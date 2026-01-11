class TaskQueue {
constructor(concurrency) {
this.concurrency=concurrency;
this.queue=[];
this.activeCount=0;
}

add(task) {
return new Promise((resolve,reject)=>{
this.queue.push({
execute:()=>task().then(resolve).catch(reject),
reject:reject
});
this.processQueue();
});
}

async processQueue() {
if (this.activeCount>=this.concurrency||this.queue.length===0) {
return;
}

const taskItem=this.queue.shift();
this.activeCount++;

try {
logger.debug("task is run.");
await taskItem.execute();
} catch (error) {
logger.error("Task error:",error);
} finally {
this.activeCount--;
this.processQueue();
}
}

getActiveCount() {
return this.activeCount;
}

getWaitingCount() {
return this.queue.length;
}

getTotalCount() {
return this.activeCount+this.queue.length;
}

getStatus() {
return {
active: this.getActiveCount(),
waiting: this.getWaitingCount(),
total: this.getTotalCount()
};
}

clearQueue() {
const clearedCount=this.queue.length;
this.queue.forEach(taskItem=>{
try{
taskItem.reject(new Error('Queue cancelled'));
}catch(e){}
});
this.queue=[];
logger.debug(`Queue cleared: ${clearedCount} tasks removed`);
return clearedCount;
}
}
